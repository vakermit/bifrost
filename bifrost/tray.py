"""System tray application for Bifrost using Toga's StatusIcon."""

import sys
from pathlib import Path

import toga
from toga.constants import COLUMN, ROW
from toga.style import Pack

from bifrost.db import Database
from bifrost.platform import get_platform


def _find_icon_path() -> str | None:
    """Find the tray icon in package resources."""
    candidates = [
        Path(__file__).parent / "resources" / "tray.png",
        Path(__file__).parent.parent / "icons" / "tray.png",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


class BifrostTrayApp(toga.App):
    """Background tray application that stays resident and provides menu access."""

    def startup(self):
        self._platform = get_platform()
        self._db = Database(self._platform.db_path())
        self._rules_window = None

        icon_path = _find_icon_path()
        icon = toga.Icon(icon_path) if icon_path else toga.Icon.DEFAULT_ICON

        tray_icon = toga.statusicons.MenuStatusIcon(
            icon=icon,
            text="Bifrost",
        )
        self.status_icons.add(tray_icon)

        status_cmd = toga.Command(self._show_status, text="Status", group=tray_icon, order=1)
        rules_cmd = toga.Command(self._show_rules, text="Edit Rules", group=tray_icon, order=2)
        browsers_cmd = toga.Command(self._show_browsers, text="Browsers", group=tray_icon, order=3)
        quit_cmd = toga.Command(self._quit, text="Quit Bifrost", group=tray_icon, order=99)

        self.status_icons.commands.add(status_cmd, rules_cmd, browsers_cmd, quit_cmd)

        self.main_window = toga.App.BACKGROUND

    def _show_status(self, command, **kwargs):
        handler = self._platform.get_current_handler()
        rule_count = len(self._db.list_rules())
        browser_count = len(self._db.list_browsers())

        window = toga.Window(title="Bifrost — Status", size=(420, 220))
        box = toga.Box(style=Pack(direction=COLUMN, margin=16))

        for text in [
            f"Version: 0.1.0",
            f"Platform: {sys.platform}",
            f"Handler: {handler or 'not registered'}",
            f"Browsers: {browser_count}",
            f"Rules: {rule_count}",
            f"Data: {self._platform.data_dir()}",
        ]:
            box.add(toga.Label(text, style=Pack(margin_bottom=6)))

        box.add(toga.Button("Close", on_press=lambda w: window.close(), style=Pack(margin_top=8)))
        window.content = box
        window.show()

    def _show_rules(self, command, **kwargs):
        if self._rules_window:
            try:
                self._rules_window.close()
            except Exception:
                pass

        self._rules_window = toga.Window(title="Bifrost — Rules", size=(700, 500))
        self._refresh_rules_window()
        self._rules_window.show()

    def _refresh_rules_window(self):
        rules = self._db.list_rules()
        box = toga.Box(style=Pack(direction=COLUMN, margin=12))

        box.add(toga.Label(
            f"Routing Rules ({len(rules)} total, priority order)",
            style=Pack(margin_bottom=8, font_weight="bold"),
        ))

        # Rules table
        table = toga.Table(
            headings=["#", "Name", "Pattern", "Type", "Browser", "Profile", "Group", "Inc."],
            data=[
                (
                    str(r.id),
                    r.name or "-",
                    r.pattern[:40],
                    r.pattern_type,
                    r.browser_name,
                    r.profile_name or "-",
                    r.group_name or "-",
                    "Yes" if r.incognito else "-",
                )
                for r in rules
            ],
            style=Pack(flex=1, margin_bottom=8),
        )
        box.add(table)
        self._rules_table = table

        # Action buttons
        btn_row = toga.Box(style=Pack(direction=ROW, margin_top=4))
        btn_row.add(toga.Button("Delete Selected", on_press=self._delete_rule, style=Pack(margin_right=8)))
        btn_row.add(toga.Button("Move Up", on_press=self._move_rule_up, style=Pack(margin_right=8)))
        btn_row.add(toga.Button("Move Down", on_press=self._move_rule_down, style=Pack(margin_right=8)))
        btn_row.add(toga.Button("Refresh", on_press=lambda w: self._refresh_rules_window()))
        box.add(btn_row)

        self._rules_window.content = box

    def _delete_rule(self, widget):
        if not self._rules_table.selection:
            return
        row = self._rules_table.selection
        rule_id = int(row[0])
        self._db.remove_rule(rule_id)
        self._refresh_rules_window()

    def _move_rule_up(self, widget):
        if not self._rules_table.selection:
            return
        row = self._rules_table.selection
        rule_id = int(row[0])
        rules = self._db.list_rules()
        for i, r in enumerate(rules):
            if r.id == rule_id and i > 0:
                self._db.reorder_rule(rule_id, rules[i - 1].priority)
                break
        self._refresh_rules_window()

    def _move_rule_down(self, widget):
        if not self._rules_table.selection:
            return
        row = self._rules_table.selection
        rule_id = int(row[0])
        rules = self._db.list_rules()
        for i, r in enumerate(rules):
            if r.id == rule_id and i < len(rules) - 1:
                self._db.reorder_rule(rule_id, rules[i + 1].priority)
                break
        self._refresh_rules_window()

    def _show_browsers(self, command, **kwargs):
        browsers = self._db.list_browsers()
        window = toga.Window(title="Bifrost — Browsers", size=(600, 350))
        box = toga.Box(style=Pack(direction=COLUMN, margin=12))

        box.add(toga.Label(
            f"Registered Browsers ({len(browsers)})",
            style=Pack(margin_bottom=8, font_weight="bold"),
        ))

        table = toga.Table(
            headings=["Name", "Type", "Platform", "Profiles"],
            data=[
                (b["name"], b["browser_type"], b["platform"], str(b["profile_count"]))
                for b in browsers
            ],
            style=Pack(flex=1, margin_bottom=8),
        )
        box.add(table)

        btn_row = toga.Box(style=Pack(direction=ROW, margin_top=4))
        btn_row.add(toga.Button("Re-Discover", on_press=self._rediscover, style=Pack(margin_right=8)))
        btn_row.add(toga.Button("Close", on_press=lambda w: window.close()))
        box.add(btn_row)

        window.content = box
        window.show()

    def _rediscover(self, widget):
        browsers = self._platform.discover_browsers()
        for browser_info in browsers:
            browser_id = self._db.upsert_browser(
                name=browser_info.name,
                browser_type=browser_info.browser_type,
                executable=browser_info.executable,
                platform=browser_info.platform,
                incognito_flag=browser_info.incognito_flag,
                profile_flag=browser_info.profile_flag,
            )
            profiles = self._platform.discover_profiles(browser_info)
            for profile in profiles:
                self._db.upsert_profile(browser_id, profile.name, profile.directory)

    def _quit(self, command, **kwargs):
        self.exit()


def run_tray():
    """Run the Bifrost system tray application."""
    app = BifrostTrayApp("Bifrost", "org.bifrost.tray")
    app.main_loop()
