"""SQLite database layer for Bifrost."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS browsers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    browser_type TEXT NOT NULL,
    executable TEXT NOT NULL,
    platform TEXT NOT NULL,
    incognito_flag TEXT NOT NULL DEFAULT '',
    profile_flag TEXT NOT NULL DEFAULT '',
    UNIQUE(browser_type, platform)
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    browser_id INTEGER NOT NULL REFERENCES browsers(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    directory TEXT NOT NULL,
    UNIQUE(browser_id, directory)
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    pattern TEXT NOT NULL,
    pattern_type TEXT NOT NULL CHECK(pattern_type IN ('domain', 'regex')),
    browser_id INTEGER NOT NULL REFERENCES browsers(id),
    profile_id INTEGER REFERENCES profiles(id),
    group_id INTEGER REFERENCES groups(id),
    incognito INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_version (
    version INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass
class RuleRow:
    id: int
    name: str | None
    pattern: str
    pattern_type: str
    browser_id: int
    profile_id: int | None
    group_id: int | None
    incognito: bool
    priority: int
    # Joined fields
    browser_name: str = ""
    browser_type: str = ""
    browser_executable: str = ""
    profile_name: str | None = None
    profile_directory: str | None = None
    group_name: str | None = None
    incognito_flag: str = ""
    profile_flag: str = ""


class Database:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            # WAL mode for concurrent CLI + handler access
            conn.execute("PRAGMA journal_mode=WAL")
            # Initialize version tracking
            row = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()
            if row[0] == 0:
                conn.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))
            row = conn.execute("SELECT COUNT(*) FROM rule_version").fetchone()
            if row[0] == 0:
                conn.execute("INSERT INTO rule_version VALUES (0)")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self._db_path), timeout=5)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _bump_rule_version(self, conn):
        conn.execute("UPDATE rule_version SET version = version + 1")

    def get_rule_version(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT version FROM rule_version").fetchone()
            return row[0] if row else 0

    # --- Browsers ---

    def upsert_browser(
        self,
        name: str,
        browser_type: str,
        executable: str,
        platform: str,
        incognito_flag: str = "",
        profile_flag: str = "",
    ) -> int:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO browsers (name, browser_type, executable, platform, incognito_flag, profile_flag)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(browser_type, platform)
                   DO UPDATE SET name=excluded.name, executable=excluded.executable,
                                incognito_flag=excluded.incognito_flag, profile_flag=excluded.profile_flag""",
                (name, browser_type, executable, platform, incognito_flag, profile_flag),
            )
            row = conn.execute(
                "SELECT id FROM browsers WHERE browser_type=? AND platform=?",
                (browser_type, platform),
            ).fetchone()
            return row[0]

    def list_browsers(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT b.*, COUNT(p.id) as profile_count
                   FROM browsers b LEFT JOIN profiles p ON p.browser_id = b.id
                   GROUP BY b.id ORDER BY b.name"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_browser_by_name(self, name: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM browsers WHERE LOWER(name)=LOWER(?) OR LOWER(browser_type)=LOWER(?)",
                (name, name),
            ).fetchone()
            return dict(row) if row else None

    def remove_browser(self, name: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM browsers WHERE LOWER(name)=LOWER(?) OR LOWER(browser_type)=LOWER(?)",
                (name, name),
            )
            return cursor.rowcount > 0

    # --- Profiles ---

    def upsert_profile(self, browser_id: int, name: str, directory: str) -> int:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO profiles (browser_id, name, directory)
                   VALUES (?, ?, ?)
                   ON CONFLICT(browser_id, directory)
                   DO UPDATE SET name=excluded.name""",
                (browser_id, name, directory),
            )
            row = conn.execute(
                "SELECT id FROM profiles WHERE browser_id=? AND directory=?",
                (browser_id, directory),
            ).fetchone()
            return row[0]

    def list_profiles(self, browser_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM profiles WHERE browser_id=? ORDER BY name", (browser_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Groups ---

    def create_group(self, name: str) -> int:
        with self._connect() as conn:
            conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
            row = conn.execute("SELECT id FROM groups WHERE name=?", (name,)).fetchone()
            return row[0]

    def list_groups(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT g.*, COUNT(r.id) as rule_count
                   FROM groups g LEFT JOIN rules r ON r.group_id = g.id
                   GROUP BY g.id ORDER BY g.name"""
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Rules ---

    def add_rule(
        self,
        pattern: str,
        pattern_type: str,
        browser_id: int,
        profile_id: int | None = None,
        group_id: int | None = None,
        incognito: bool = False,
        name: str | None = None,
    ) -> int:
        with self._connect() as conn:
            # Get next priority
            row = conn.execute("SELECT COALESCE(MAX(priority), 0) + 1 FROM rules").fetchone()
            priority = row[0]
            conn.execute(
                """INSERT INTO rules (name, pattern, pattern_type, browser_id, profile_id,
                   group_id, incognito, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (name, pattern, pattern_type, browser_id, profile_id, group_id, int(incognito), priority),
            )
            self._bump_rule_version(conn)
            row = conn.execute("SELECT last_insert_rowid()").fetchone()
            return row[0]

    def list_rules(self) -> list[RuleRow]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT r.*, b.name as browser_name, b.browser_type, b.executable as browser_executable,
                          b.incognito_flag, b.profile_flag,
                          p.name as profile_name, p.directory as profile_directory,
                          g.name as group_name
                   FROM rules r
                   JOIN browsers b ON b.id = r.browser_id
                   LEFT JOIN profiles p ON p.id = r.profile_id
                   LEFT JOIN groups g ON g.id = r.group_id
                   ORDER BY r.priority"""
            ).fetchall()
            return [
                RuleRow(
                    id=r["id"],
                    name=r["name"],
                    pattern=r["pattern"],
                    pattern_type=r["pattern_type"],
                    browser_id=r["browser_id"],
                    profile_id=r["profile_id"],
                    group_id=r["group_id"],
                    incognito=bool(r["incognito"]),
                    priority=r["priority"],
                    browser_name=r["browser_name"],
                    browser_type=r["browser_type"],
                    browser_executable=r["browser_executable"],
                    profile_name=r["profile_name"],
                    profile_directory=r["profile_directory"],
                    group_name=r["group_name"],
                    incognito_flag=r["incognito_flag"],
                    profile_flag=r["profile_flag"],
                )
                for r in rows
            ]

    def remove_rule(self, rule_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM rules WHERE id=?", (rule_id,))
            if cursor.rowcount > 0:
                self._bump_rule_version(conn)
                return True
            return False

    def reorder_rule(self, rule_id: int, new_position: int) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT priority FROM rules WHERE id=?", (rule_id,)).fetchone()
            if not row:
                return False
            old_priority = row[0]

            if new_position > old_priority:
                conn.execute(
                    "UPDATE rules SET priority = priority - 1 WHERE priority > ? AND priority <= ?",
                    (old_priority, new_position),
                )
            elif new_position < old_priority:
                conn.execute(
                    "UPDATE rules SET priority = priority + 1 WHERE priority >= ? AND priority < ?",
                    (new_position, old_priority),
                )
            else:
                return True

            conn.execute("UPDATE rules SET priority=? WHERE id=?", (new_position, rule_id))
            self._bump_rule_version(conn)
            return True

    # --- Config ---

    def get_config(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_config(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
