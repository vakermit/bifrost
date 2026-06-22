"""Security layer for Bifrost — URL validation, regex safety."""

import re
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

# Patterns that indicate catastrophic backtracking risk
DANGEROUS_REGEX_PATTERNS = [
    re.compile(r"\(\.\*\)\+"),       # (.*)+
    re.compile(r"\(\.\+\)\+"),       # (.+)+
    re.compile(r"\([^)]*\+[^)]*\)\+"),  # (X+)+ nested quantifiers
    re.compile(r"\([^)]*\*[^)]*\)\+"),  # (X*)+
    re.compile(r"\([^)]*\+[^)]*\)\*"),  # (X+)*
    re.compile(r"\([^)]*\*[^)]*\)\*"),  # (X*)*
]

MAX_URL_LENGTH = 65536  # 64KB max URL length


def validate_url(url: str) -> tuple[bool, str]:
    """Validate a URL is safe to process. Returns (is_valid, reason)."""
    if not url:
        return False, "Empty URL"

    if len(url) > MAX_URL_LENGTH:
        return False, f"URL exceeds maximum length ({MAX_URL_LENGTH} chars)"

    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "Malformed URL"

    if not parsed.scheme:
        return False, "No URL scheme"

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False, f"Blocked scheme: {parsed.scheme} (only http/https allowed)"

    return True, "OK"


def validate_regex(pattern: str) -> tuple[bool, str]:
    """Validate a regex pattern is safe to compile and use. Returns (is_valid, reason)."""
    if not pattern:
        return False, "Empty pattern"

    for dangerous in DANGEROUS_REGEX_PATTERNS:
        if dangerous.search(pattern):
            return False, f"Pattern contains nested quantifiers which can cause catastrophic backtracking"

    try:
        re.compile(pattern)
    except re.error as e:
        return False, f"Invalid regex: {e}"

    return True, "OK"


def sanitize_url_for_log(url: str, max_length: int = 512, redact_query: bool = True) -> str:
    """Sanitize a URL for logging — truncate and optionally redact query string."""
    if not url:
        return ""

    if redact_query:
        try:
            parsed = urlparse(url)
            if parsed.query:
                url = url.split("?")[0] + "?[REDACTED]"
        except ValueError:
            pass

    if len(url) > max_length:
        url = url[:max_length] + "...[TRUNCATED]"

    # Remove newlines to prevent log injection
    url = url.replace("\n", "").replace("\r", "")

    return url
