import re

def sanitize_input(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = re.sub(r"<[^>]+>", "", text)

    text = re.sub(
        r"(?i)(ignore previous|disregard|abaikan instruksi|abaikan aturan|jailbreak|bypass|override|"
        r"act as|pretend|roleplay|forget system|prompt injection).*",
        "",
        text,
    )

    return text.strip()
