"""Input sanitization and PII masking utilities for UnderCover backend."""

import re

# Match dangerous HTML tags and their inner contents
DANGEROUS_BLOCK_PATTERN = re.compile(
    r"<(script|iframe|style|object|embed|applet)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Match standalone / unclosed dangerous tags
DANGEROUS_TAG_PATTERN = re.compile(
    r"</?(?:script|iframe|style|object|embed|applet|svg|form)[^>]*>",
    re.IGNORECASE,
)

# Match inline event handlers (e.g., onload=..., onerror=...)
EVENT_HANDLER_PATTERN = re.compile(
    r"""\bon\w+\s*=\s*(?:'[^']*'|"[^"]*"|[^\s>]+)""",
    re.IGNORECASE,
)

# Match javascript: or vbscript: pseudoprotocols
JS_SCHEME_PATTERN = re.compile(
    r"(?:javascript|vbscript|data\s*:\s*text/html)\s*:",
    re.IGNORECASE,
)

# Match standard 16-digit credit card numbers
# (grouped with dashes, spaces, or contiguous)
CREDIT_CARD_PATTERN = re.compile(r"\b(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})[-\s]?(\d{4})\b")


def sanitize_text(text: str) -> str:
    """Strip dangerous HTML tags, scripts, and script execution vectors."""
    if not text:
        return ""
    # Strip dangerous blocks with content
    cleaned = DANGEROUS_BLOCK_PATTERN.sub("", text)
    # Strip standalone dangerous tags
    cleaned = DANGEROUS_TAG_PATTERN.sub("", cleaned)
    # Strip event handlers
    cleaned = EVENT_HANDLER_PATTERN.sub("", cleaned)
    # Strip javascript schemes
    cleaned = JS_SCHEME_PATTERN.sub("", cleaned)
    return cleaned.strip()


def mask_financial_pii(text: str) -> str:
    """Mask 16-digit payment card numbers, preserving only the last 4 digits."""
    if not text:
        return ""

    def _replace_cc(match: re.Match[str]) -> str:
        last4 = match.group(4)
        return f"[REDACTED CARD: ****-****-****-{last4}]"

    return CREDIT_CARD_PATTERN.sub(_replace_cc, text)


def clean_user_input(text: str) -> str:
    """Apply both HTML sanitization and financial PII masking to user input."""
    if not text:
        return ""
    sanitized = sanitize_text(text)
    return mask_financial_pii(sanitized)
