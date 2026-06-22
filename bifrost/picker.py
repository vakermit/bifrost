"""Picker window — Toga-based native browser/profile chooser for unmatched URLs."""

import re
from urllib.parse import urlparse

import toga
from toga.constants import COLUMN, ROW, RIGHT
from toga.style import Pack

from bifrost.db import Database
from bifrost.security import validate_regex


def show_picker_window(url: str, db: Database) -> dict | None:
    """Show a native picker window and return the user's choice, or None if cancelled."""
    result = {"choice": None}

    browsers = db.list_browsers()
    browser_profiles: dict[int, list[dict]] = {}
    for b in browsers:
        browser_profiles[b["id"]] = db.list_profiles(b["id"])

    # Build flat list of selectable options: "Browser" and "Browser — Profile"
    options = []
    option_map = []

    for b in browsers:
        options.append(b["name"])
        option_map.append((b, None))
        for p in browser_profiles.get(b["id"], []):
            options.append(f"  {b['name']} — {p['name']}")
            option_map.append((b, p))

    class PickerApp(toga.App):
        def startup(self):
            self.main_window = toga.MainWindow(
                title="Bifrost — Choose Browser",
                size=(500, 460),
                resizable=False,
            )

            # URL display
            url_label = toga.Label(
                "URL:", style=Pack(margin_bottom=4, font_weight="bold")
            )
            url_input = toga.MultilineTextInput(
                value=url,
                readonly=True,
                style=Pack(height=50, margin_bottom=4, font_family="monospace"),
            )
            copy_btn = toga.Button(
                "Copy URL",
                on_press=self._copy_url,
                style=Pack(margin_bottom=8),
            )
            self._url = url
            self._copy_btn = copy_btn

            # Browser/profile selection
            select_label = toga.Label(
                "Open with:", style=Pack(margin_bottom=4, font_weight="bold")
            )
            self._selection = toga.Selection(
                items=options,
                style=Pack(margin_bottom=8, flex=1),
            )

            # Incognito toggle
            self._incognito = toga.Switch(
                "Open in private / incognito mode",
                style=Pack(margin_bottom=12),
            )

            # Remember section
            remember_label = toga.Label(
                "Remember this choice:",
                style=Pack(margin_bottom=4, font_weight="bold"),
            )
            self._remember = toga.Switch("Remember", style=Pack(margin_bottom=4))

            self._remember_type = toga.Selection(
                items=["This domain", "This exact URL", "Custom regex"],
                style=Pack(margin_bottom=4),
            )

            try:
                parsed = urlparse(url)
                domain = parsed.hostname or ""
                default_regex = f"^https?://{re.escape(domain)}.*"
            except ValueError:
                default_regex = ""

            self._regex_input = toga.TextInput(
                value=default_regex,
                placeholder="Custom regex pattern",
                style=Pack(margin_bottom=8, flex=1),
            )

            # Buttons
            open_btn = toga.Button(
                "Open",
                on_press=self._on_open,
                style=Pack(flex=1, margin_right=4),
            )
            cancel_btn = toga.Button(
                "Cancel",
                on_press=self._on_cancel,
                style=Pack(flex=1, margin_left=4),
            )
            button_row = toga.Box(
                children=[open_btn, cancel_btn],
                style=Pack(direction=ROW, margin_top=8),
            )

            content = toga.Box(
                children=[
                    url_label,
                    url_input,
                    copy_btn,
                    select_label,
                    self._selection,
                    self._incognito,
                    remember_label,
                    self._remember,
                    self._remember_type,
                    self._regex_input,
                    button_row,
                ],
                style=Pack(direction=COLUMN, margin=16),
            )

            self.main_window.content = content
            self.main_window.show()

        def _copy_url(self, widget):
            import subprocess
            import sys

            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=self._url.encode(), check=False)
            elif sys.platform == "win32":
                subprocess.run(["clip"], input=self._url.encode(), check=False)
            self._copy_btn.text = "Copied!"

        def _on_open(self, widget):
            idx = (
                options.index(self._selection.value)
                if self._selection.value in options
                else -1
            )
            if idx < 0:
                return

            browser, profile = option_map[idx]
            incognito = self._incognito.value

            choice = {
                "browser": browser["name"],
                "browser_id": browser["id"],
                "executable": browser["executable"],
                "incognito": incognito,
                "incognito_flag": browser["incognito_flag"],
            }
            if profile:
                choice.update(
                    {
                        "profile": profile["name"],
                        "profile_id": profile["id"],
                        "profile_dir": profile["directory"],
                        "profile_flag": browser["profile_flag"],
                    }
                )

            if self._remember.value:
                _save_remember_rule(
                    db,
                    url,
                    self._remember_type.value,
                    self._regex_input.value,
                    choice,
                    incognito,
                )

            result["choice"] = choice
            self.main_window.close()
            self.exit()

        def _on_cancel(self, widget):
            self.main_window.close()
            self.exit()

    app = PickerApp("Bifrost Picker", "org.bifrost.picker")
    app.main_loop()
    return result["choice"]


def _save_remember_rule(
    db: Database,
    url: str,
    remember_type: str,
    custom_regex: str,
    choice: dict,
    incognito: bool,
):
    """Save a 'remember' choice as a new rule."""
    if remember_type == "This exact URL":
        pattern = f"^{re.escape(url)}$"
        pattern_type = "regex"
    elif remember_type == "This domain":
        try:
            parsed = urlparse(url)
            pattern = f"*.{parsed.hostname}" if parsed.hostname else url
        except ValueError:
            pattern = url
        pattern_type = "domain"
    elif remember_type == "Custom regex":
        valid, reason = validate_regex(custom_regex)
        if not valid:
            return
        pattern = custom_regex
        pattern_type = "regex"
    else:
        return

    db.add_rule(
        pattern=pattern,
        pattern_type=pattern_type,
        browser_id=choice["browser_id"],
        profile_id=choice.get("profile_id"),
        incognito=incognito,
    )
