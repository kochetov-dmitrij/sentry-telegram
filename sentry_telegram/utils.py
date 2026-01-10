import base64


class TextProcessor:
    @staticmethod
    def escape_markdown(text: str) -> str:
        escaped_chars = set(r"`*_{[")
        return "".join(
            f"\\{character}" if character in escaped_chars else character
            for character in text
        )

    @staticmethod
    def b64encode(string: str) -> str:
        return base64.b64encode(string.encode()).decode()

    @staticmethod
    def truncate(text: str, max_length: int, warning_text: str = "...") -> str:
        if len(text) > max_length:
            text = text[: max(0, max_length - len(warning_text))] + warning_text
        return text
