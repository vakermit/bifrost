"""System tray application for Bifrost using Toga's StatusIcon."""

import subprocess
import sys
from pathlib import Path

import toga
from toga.constants import COLUMN
from toga.style import Pack

from bifrost.db import Database
from bifrost.platform import get_platform


def _find_icon_path() -> str | None:
    """Find the tray icon — check project icons/ dir and package resources."""
    candidates = [
        Path(__file__).parent.parent / "icons" / "tray.png",
        Path(__file__).parent / "resources" / "tray.png",
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

        # Use the Bifrost icon for the tray if available
        icon_path = _find_icon_path()
        icon = toga.Icon(icon_path) if icon_path else toga.Icon.DEFAULT_ICON

        tray_icon = toga.statusicons.MenuStatusIcon(
            icon=icon,
            text="Bifrost",
        )
        self.status_icons.add(tray_icon)

        # Commands attached to the tray menu via the MenuStatusIcon as group
        toga.Command(
            self._show_status,
            text="Status",
            group=tray_icon,
            order=1,
        )
        toga.Command(
            self._show_preferences,
            text="Preferences",
            group=tray_icon,
            order=2,
        )
        toga.Command(
            self._quit,
            text="Quit Bifrost",
            group=tray_icon,
            order=99,
        )

        # Background app — no dock icon, tray only
        self.main_window = toga.App.BACKGROUND

    def _show_status(self, command, **kwargs):
        handler = self._platform.get_current_handler()
        rule_count = len(self._db.list_rules())
        browser_count = len(self._db.list_browsers())

        window = toga.Window(title="Bifrost Status", size=(400, 250))

        labels = [
            f"Handler: {handler or 'not registered'}",
            f"Browsers: {browser_count}",
            f"Rules: {rule_count}",
            f"Data: {self._platform.data_dir()}",
        ]

        content = toga.Box(style=Pack(direction=COLUMN, margin=16))
        for text in labels:
            content.add(toga.Label(text, style=Pack(margin_bottom=8)))

        close_btn = toga.Button("Close", on_press=lambda w: window.close())
        content.add(close_btn)

        window.content = content
        window.show()

    def _show_preferences(self, command, **kwargs):
        if sys.platform == "darwin":
            subprocess.Popen(
                ["osascript", "-e",
                 'tell application "Terminal" to do script "bifrost rule list && bifrost browser list"'],
                start_new_session=True,
            )
        elif sys.platform == "win32":
            subprocess.Popen(
                ["cmd", "/c", "start", "cmd", "/k",
                 "bifrost rule list && bifrost browser list"],
                start_new_session=True,
            )

    def _quit(self, command, **kwargs):
        self.exit()


def run_tray():
    """Run the Bifrost system tray application."""
    app = BifrostTrayApp(
        "Bifrost",
        "org.bifrost.tray",
    )
    app.main_loop()
