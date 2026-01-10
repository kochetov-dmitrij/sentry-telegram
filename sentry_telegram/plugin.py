import logging
from collections import defaultdict
from urllib.error import HTTPError as UrllibHTTPError

from django import forms
from django.utils.translation import gettext_lazy as _
from jinja2 import Environment
from requests.exceptions import HTTPError, SSLError
from sentry.exceptions import InvalidIdentity, PluginError
from sentry.http import safe_urlopen
from sentry.plugins.base.structs import Notification
from sentry.plugins.bases import notify
from sentry.shared_integrations.exceptions import ApiError
from sentry.utils.http import absolute_uri
from sentry.utils.safe import safe_execute

from . import __doc__ as package_doc
from . import __version__
from .constants import TELEGRAM_MESSAGE_MAX_LENGTH
from .utils import TextProcessor


class TelegramNotificationsOptionsForm(notify.NotificationConfigurationForm):
    api_origin = forms.CharField(
        label=_("Telegram API origin"),
        widget=forms.TextInput(attrs={"placeholder": "https://api.telegram.org"}),
        initial="https://api.telegram.org",
    )
    api_token = forms.CharField(
        label=_("BotAPI token"),
        widget=forms.TextInput(
            attrs={"placeholder": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"}
        ),
        help_text=_(
            "Read more: https://core.telegram.org/bots/api#authorizing-your-bot"
        ),
    )
    receivers = forms.CharField(
        label=_("Receivers"),
        widget=forms.Textarea(attrs={"class": "span6"}),
        help_text=_(
            "Enter receivers IDs (one per line). Personal messages, group chats and channels also available. "
            'If you want to specify a thread ID, separate it with "/" (e.g. "12345/12").'
        ),
    )
    message_template = forms.CharField(
        label=_("Message template"),
        widget=forms.Textarea(attrs={"class": "span4"}),
        help_text=_(
            "Jinja2 format template. Available names are: "
            "{{project_name}}, {{url}}, {{title}}, {{message}}, {{tags.%your_tag%}}, {{rules}}. "
            "Available filters: escape_markdown, b64encode."
        ),
        initial="*[Sentry]* {{ project_name }} {{ tags.level }}: *{{ title }}*\n```\n{{ message }}\n```\n{{ url }}",
    )


class TelegramNotificationsPlugin(notify.NotificationPlugin):
    title = "Telegram Notifications"
    slug = "sentry_telegram"
    description = package_doc
    version = __version__
    author = "kochetov-dmitrij"
    author_email = "d.kochetov98@gmail.com"
    resource_links = [
        ("Source", "https://github.com/kochetov-dmitrij/sentry-telegram"),
        ("Forked From", "https://github.com/butorov/sentry-telegram"),
    ]

    conf_key = "sentry_telegram"
    conf_title = title

    project_conf_form = TelegramNotificationsOptionsForm

    logger = logging.getLogger("sentry.plugins.sentry_telegram")

    def is_configured(self, project, **kwargs):
        return bool(
            self.get_option("api_token", project)
            and self.get_option("receivers", project)
        )

    def get_config(self, project, **kwargs):
        form = self.project_conf_form()
        config = []

        for field_name in ["api_origin", "api_token", "receivers", "message_template"]:
            field = form.fields[field_name]
            config_item = {
                "name": field_name,
                "label": field.label,
                "type": (
                    "textarea" if isinstance(field.widget, forms.Textarea) else "text"
                ),
                "validators": [],
                "required": field.required,
                "placeholder": field.widget.attrs.get("placeholder"),
                "default": field.initial,
                "help": field.help_text,
            }
            config.append(config_item)

        return config

    def compile_message_text(self, message_template: str, message_params: dict) -> str:
        jinja_env = Environment()
        jinja_env.filters["escape_markdown"] = TextProcessor.escape_markdown
        jinja_env.filters["b64encode"] = TextProcessor.b64encode
        jinja_env.filters["truncate"] = TextProcessor.truncate

        message_text = jinja_env.from_string(message_template).render(**message_params)
        message_text = TextProcessor.truncate(
            message_text, TELEGRAM_MESSAGE_MAX_LENGTH, "... (truncated)"
        )
        return message_text

    def build_message(self, event, notification):
        event_tags = defaultdict(lambda: "<nil>", {k: v for k, v in event.tags})

        project_name = event.group.project.name
        issue_url = event.group.get_absolute_url()

        rules = [
            {
                "label": rule.label,
                "url": absolute_uri(
                    f"/organizations/sentry/alerts/rules/{project_name}/{rule.id}/details/"
                ),
            }
            for rule in notification.rules
        ]

        message_params = {
            "title": event.title,
            "project_name": project_name,
            "message": event.message,
            "tags": event_tags,
            "url": issue_url,
            "rules": rules,
            "event": event,
            "notification": notification,
        }
        text = self.compile_message_text(
            self.get_message_template(event.group.project),
            message_params,
        )

        return {
            "text": text,
            "parse_mode": "Markdown",
        }

    def build_url(self, project):
        return "%s/bot%s/sendMessage" % (
            self.get_option("api_origin", project),
            self.get_option("api_token", project),
        )

    def get_message_template(self, project):
        return self.get_option("message_template", project)

    def get_receivers(self, project) -> list[list[str, str]]:
        receivers = self.get_option("receivers", project).strip()
        if not receivers:
            return []
        return list(
            [
                line.strip().split("/", maxsplit=1)
                for line in receivers.splitlines()
                if line.strip()
            ]
        )

    def send_message(self, url, payload, receiver: list[str, str]):
        payload["chat_id"] = receiver[0]
        if len(receiver) > 1:
            payload["message_thread_id"] = receiver[1]
        self.logger.debug("Sending message to %s" % receiver)
        response = safe_urlopen(
            method="POST",
            url=url,
            json=payload,
        )
        self.logger.debug(
            "Response code: %s, content: %s" % (response.status_code, response.content)
        )
        if response.status_code > 299:
            raise ConnectionError(response.content)

    def notify(self, notification: Notification, raise_exception: bool = False) -> None:
        event = notification.event
        try:
            self.notify_users(
                event=event,
                notification=notification,
            )
        except (
            ApiError,
            HTTPError,
            InvalidIdentity,
            PluginError,
            SSLError,
            UrllibHTTPError,
        ) as err:
            self.logger.info(
                "notification-plugin.notify-failed",
                extra={
                    "error": str(err),
                    "plugin": self.slug,
                    "project_id": event.group.project_id,
                    "organization_id": event.group.project.organization_id,
                },
            )
            if raise_exception:
                raise

    def notify_users(self, event, notification):
        self.logger.debug("Received notification for event: %s" % event)
        receivers = self.get_receivers(event.group.project)
        self.logger.debug(
            "for receivers: %s"
            % ", ".join(["/".join(item) for item in receivers] or ())
        )
        payload = self.build_message(event, notification)
        self.logger.debug("Built payload: %s" % payload)
        url = self.build_url(event.group.project)
        self.logger.debug("Built url: %s" % url)
        for receiver in receivers:
            safe_execute(self.send_message, url, payload, receiver)
