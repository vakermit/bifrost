"""System tray application for Bifrost using Toga's StatusIcon."""

import subprocess
import sys

import toga
from toga.constants import COLUMN
from toga.style import Pack

from bifrost.db import Database
from bifrost.platform import get_platform


class BifrostTrayApp(toga.App):
    """Background tray application that stays resident and provides menu access."""

    def startup(self):
        self._platform = get_platform()
        self._db = Database(self._platform.db_path())

        # Status commands
        status_cmd = toga.Command(
            self._show_status,
            text="Status",
            group=toga.Group.COMMANDS,
        )
        prefs_cmd = toga.Command(
            self._show_preferences,
            text="Preferences",
            group=toga.Group.COMMANDS,
        )
        quit_cmd = toga.Command(
            self._quit,
            text="Quit Bifrost",
            group=toga.Group.COMMANDS,
        )

        self.status_icons.add(
            toga.statusicons.MenuStatusIcon(
                icon=toga.Icon.DEFAULT_ICON,
                commands=[status_cmd, prefs_cmd, quit_cmd],
            )
        )

        # No main window — tray-only app
        self.main_window = None

    def _show_status(self, command, **kwargs):
        handler = self._platform.get_current_handler()
        rule_count = len(self._db.list_rules())
        browser_count = len(self._db.list_browsers())

        self.main_window = toga.MainWindow(title="Bifrost Status", size=(400, 250))

        labels = [
            f"Handler: {handler or 'not registered'}",
            f"Browsers: {browser_count}",
            f"Rules: {rule_count}",
            f"Data: {self._platform.data_dir()}",
        ]

        content = toga.Box(style=Pack(direction=COLUMN, padding=16))
        for text in labels:
            content.add(toga.Label(text, style=Pack(padding_bottom=8)))

        close_btn = toga.Button("Close", on_press=lambda w: self.main_window.close())
        content.add(close_btn)

        self.main_window.content = content
        self.main_window.show()

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
    app = BifrostTrayApp("Bifrost", "org.bifrost.tray")
    app.main_loop()
