"""URL handler — the core routing processor for Bifrost."""

import json
import logging
import sys
import time
from pathlib import Path

from bifrost.db import Database
from bifrost.platform import get_platform
from bifrost.rules import RuleEngine
from bifrost.security import sanitize_url_for_log, validate_url

logger = logging.getLogger("bifrost")

# Crash tracking for dead-letter fallback
_crash_times: list[float] = []
MAX_CRASHES = 3
CRASH_WINDOW = 60  # seconds


def handle_url(url: str, db: Database | None = None, show_picker: bool = True):
    """Process a URL: validate, match rules, launch browser or show picker."""
    platform = get_platform()

    # FIRST ACTION: capture the raw URL before any processing
    _write_last_url(url, platform.data_dir())

    # Validate URL scheme
    valid, reason = validate_url(url)
    if not valid:
        logger.warning("Rejected URL: %s — %s", sanitize_url_for_log(url), reason)
        return

    # Check crash rate — if too many crashes, fall back to default browser
    if _check_crash_rate():
        logger.error("Too many crashes in %ds — falling back to default browser", CRASH_WINDOW)
        platform.open_default_browser(url)
        return

    try:
        if db is None:
            db = Database(platform.db_path())

        engine = RuleEngine(db)
        result = engine.match(url)

        if result:
            _launch_matched(result, url, platform, db)
        else:
            _handle_no_match(url, platform, db, show_picker)

    except Exception:
        logger.exception("Handler crash for URL: %s", sanitize_url_for_log(url))
        _record_crash()
        # Fallback: open in default browser
        try:
            platform.open_default_browser(url)
        except Exception:
            logger.exception("Fallback browser launch also failed")


def _launch_matched(result, url: str, platform, db: Database):
    """Launch a matched rule's browser/profile."""
    rule = result.rule
    log_url = sanitize_url_for_log(url, redact_query=db.get_config("verbose_log") != "true")
    logger.info(
        "Routed: %s → %s%s%s (rule: %s)",
        log_url,
        rule.browser_name,
        f" [{rule.profile_name}]" if rule.profile_name else "",
        " [incognito]" if rule.incognito else "",
        rule.name or f"#{rule.id}",
    )
    platform.launch_browser(
        executable=rule.browser_executable,
        url=url,
        profile_dir=rule.profile_directory,
        profile_flag=rule.profile_flag if rule.profile_directory else None,
        incognito=rule.incognito,
        incognito_flag=rule.incognito_flag if rule.incognito else None,
    )


def _handle_no_match(url: str, platform, db: Database, show_picker: bool):
    """Handle unmatched URLs — default browser or picker."""
    default_action = db.get_config("default_action", "ask")

    if default_action == "ask" and show_picker:
        from bifrost.picker import show_picker_window

        choice = show_picker_window(url, db)
        if choice:
            log_url = sanitize_url_for_log(url, redact_query=db.get_config("verbose_log") != "true")
            logger.info("Picker: %s → %s%s", log_url, choice.get("browser", ""),
                       f" [{choice.get('profile', '')}]" if choice.get("profile") else "")
            platform.launch_browser(
                executable=choice["executable"],
                url=url,
                profile_dir=choice.get("profile_dir"),
                profile_flag=choice.get("profile_flag"),
                incognito=choice.get("incognito", False),
                incognito_flag=choice.get("incognito_flag"),
            )
    else:
        # Default browser/profile
        default_browser = db.get_config("default_browser")
        if default_browser:
            browser = db.get_browser_by_name(default_browser)
            if browser:
                platform.launch_browser(executable=browser["executable"], url=url)
                return
        platform.open_default_browser(url)


def _write_last_url(url: str, data_dir: Path):
    """Atomically write the last received URL for crash recovery."""
    try:
        last_url_file = data_dir / "last_url.txt"
        last_url_file.write_text(url, encoding="utf-8")
    except OSError:
        pass


def _check_crash_rate() -> bool:
    """Check if we've crashed too many times recently."""
    now = time.time()
    _crash_times[:] = [t for t in _crash_times if now - t < CRASH_WINDOW]
    return len(_crash_times) >= MAX_CRASHES


def _record_crash():
    _crash_times.append(time.time())
