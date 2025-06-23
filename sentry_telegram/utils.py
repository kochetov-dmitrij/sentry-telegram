import base64


def escape_markdown(text: str) -> str:
    escaped_chars = set(r"`*_{[")
    return "".join(
        f"\\{character}" if character in escaped_chars else character
        for character in text
    )


def b64encode(string: str) -> str:
    return base64.b64encode(string.encode()).decode()
