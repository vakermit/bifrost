"""Rule matching engine for Bifrost."""

import fnmatch
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bifrost.db import Database, RuleRow


@dataclass
class MatchResult:
    rule: RuleRow
    matched: bool = True


class RuleEngine:
    def __init__(self, db: Database):
        self._db = db
        self._rules: list[RuleRow] = []
        self._compiled: list[tuple[RuleRow, re.Pattern | None]] = []
        self._version = -1
        self._reload()

    def _reload(self):
        current_version = self._db.get_rule_version()
        if current_version == self._version:
            return
        self._rules = self._db.list_rules()
        self._compiled = []
        for rule in self._rules:
            if rule.pattern_type == "regex":
                try:
                    compiled = re.compile(rule.pattern, re.IGNORECASE)
                except re.error:
                    compiled = None
            else:
                compiled = None
            self._compiled.append((rule, compiled))
        self._version = current_version

    def match(self, url: str) -> MatchResult | None:
        """Match a URL against rules in priority order. Returns first match or None."""
        self._reload()

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or ""
        except ValueError:
            return None

        for rule, compiled in self._compiled:
            if rule.pattern_type == "domain":
                if self._match_domain(rule.pattern, hostname):
                    return MatchResult(rule=rule)
            elif rule.pattern_type == "regex":
                if compiled and compiled.search(url):
                    return MatchResult(rule=rule)

        return None

    @staticmethod
    def _match_domain(pattern: str, hostname: str) -> bool:
        """Match a domain pattern against a hostname.

        Supports:
        - Exact match: "example.com"
        - Wildcard: "*.example.com" matches both "sub.example.com" AND "example.com"
        - Full glob: "*.slack.*"
        """
        pattern = pattern.lower().strip()
        hostname = hostname.lower().strip()

        if pattern == hostname:
            return True

        if fnmatch.fnmatch(hostname, pattern):
            return True

        # "*.example.com" should also match "example.com" itself
        if pattern.startswith("*."):
            bare_domain = pattern[2:]
            if hostname == bare_domain:
                return True

        return False
