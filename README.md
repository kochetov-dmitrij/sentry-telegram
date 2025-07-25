# Sentry Telegram Plugin

Forked from https://github.com/butorov/sentry-telegram.

Plugin for Sentry which allows sending notifications via the [Telegram](https://telegram.org/) messenger.

As any plugins installation is only available for [self-hosted Sentry](https://github.com/getsentry/self-hosted) instances.

The plugin has been tested with the most recent version of Sentry available at the time - 25.3.0.

## Features

- Sending notifications about issues to one or many Telegram users and/or groups.
- Sending notifications to particular threads (Topics) in chats.
- Customizable message template (Jinja2) with placeholders for the project name, issue URL, title, error message, tags, triggered rules.
- Support for Markdown formatting in the message template.

## Build

Bump the version in the `sentry_telegram/__init__.py` file for a new release.

Build the plugin via Docker, this will create a `dist/` directory with the plugin package:
```
rm -rf dist
docker run \
  -it \
  --rm \
  -v $(pwd):/app \
  -w /app \
  python:3.11.13-alpine3.22 \
  sh -c "pip install build && python -m build"
```

## Publish

Publish the build Python package in the `dist/` directory to the [PyPI GitLab registry](https://gitlab.com/<repo>/-/packages/<id>):

```
GITLAB_TOKEN=<your_gitlab_personal_token>
REGISTRY_URL=https://gitlab.com/api/v4/projects/<project_id>/packages/pypi

docker run \
  -it \
  --rm \
  -v $(pwd):/app \
  -w /app \
  -e TWINE_USERNAME=gitlab-ci-token \
  -e TWINE_PASSWORD=$GITLAB_TOKEN \
  python:3.11.13-alpine3.22 \
  sh -c "pip install twine && twine upload --verbose --repository-url $REGISTRY_URL dist/*"
```

## Installation

### [Option A] Install from PyPI

Manually SSH into a Sentry server and run the following commands:

```bash
GITLAB_TOKEN=<your_gitlab_personal_token_with_read_api_scope>
REGISTRY_URL="https://__token__:$GITLAB_TOKEN@gitlab.com/api/v4/projects/<project_id>/packages/pypi/simple"

cd /opt/self-hosted
[ ! -f sentry/enhance-image.sh ] && cp sentry/enhance-image.example.sh sentry/enhance-image.sh
echo "pip install sentry-telegram==1.0.0 --index-url $REGISTRY_URL" >> sentry/enhance-image.sh
docker compose build --no-cache web && docker compose up -d --force-recreate
```

### [Option B] Install from a file

Copy the plugin package to the Sentry server:

```bash
scp dist/sentry_telegram-1.0.0.tar.gz <sentry-server-ip>:/opt/self-hosted/sentry/
```

Manually SSH into a Sentry server and run the following commands:

```bash
cd /opt/self-hosted
[ ! -f sentry/enhance-image.sh ] && cp sentry/enhance-image.example.sh sentry/enhance-image.sh
echo "pip install sentry_telegram-1.0.0.tar.gz" >> sentry/enhance-image.sh
docker compose build --no-cache web && docker compose up -d --force-recreate
```

## Configuration

You must repeat this for all projects separately

1. Enable the plugin \
   `Project Settings` -> `Legacy Integrations` -> `Telegram Notifications` check the box

2. Open the plugin settings \
   `Project Settings` -> `Alerts Settings` -> `TELEGRAM NOTIFICATIONS`

3. Insert the `BotAPI token` and `Receivers` (chat id)

4. Insert a custom message template. For example [this one](./examples/template-1.jinja)

5. Click `Save Changes`

6. Click `Test Plugin` for triggering a test issue, confirm the alert message is received in Telegram
