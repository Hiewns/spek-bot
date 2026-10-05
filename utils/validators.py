import re
from typing import Tuple, Optional


class TextProcessor:
    """Handles text cleaning, truncation, and validation before TTS generation."""

    def __init__(self, max_length: int = 500):
        self.max_length = max_length

    @staticmethod
    def clean_text(text: str) -> str:
        """Remove mentions, URLs, custom emojis, and excessive markdown/whitespace."""
        if not text:
            return ""

        # Remove spoiler tags ||hidden|| -> keep text or strip? Strip content inside or delimiters
        # Let's remove spoiler delimiters
        text = text.replace("||", "")

        # Remove @mentions (<@123456>, <@!123456>, <@&role>)
        text = re.sub(r"<@[!&]?\d+>", "", text)

        # Remove channel mentions (<#123456>)
        text = re.sub(r"<#\d+>", "", text)

        # Remove custom emojis (<:name:123456> or <a:name:123456>)
        text = re.sub(r"<a?:\w+:\d+>", "", text)

        # Remove URLs (http/https/ftp)
        text = re.sub(r"https?://\S+|ftp://\S+", "", text)

        # Remove code blocks ```code``` and inline code `code`
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`[^`]*`", "", text)

        # Remove markdown symbols (*, _, ~, #, >) without leaving trailing spaces before punctuation
        text = re.sub(r"[*_~#>`]", "", text)

        # Normalize spaces before punctuation (e.g. "word ." -> "word.")
        text = re.sub(r"\s+([.,!?;:])", r"\1", text)

        # Normalize repeated whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def truncate(self, text: str, max_length: Optional[int] = None) -> str:
        """Truncate text to max_length and add ellipsis if truncated."""
        limit = max_length if max_length is not None else self.max_length
        if len(text) > limit:
            return text[:limit].rstrip() + "..."
        return text

    def validate(self, text: str) -> Tuple[bool, Optional[str]]:
        """Check if text is valid for TTS synthesis."""
        if not text or len(text.strip()) == 0:
            return False, "Message is empty or contains only stripped content (links/mentions)."

        if len(text) > 2000:
            return False, "Message exceeds Discord maximum length (2000 characters)."

        cleaned = self.clean_text(text)
        if not cleaned:
            return False, "Message contains no readable text after filtering."

        return True, None
