"""macOS platform implementation for Bifrost."""

import json
import subprocess
from pathlib import Path

from bifrost.platform_base import BrowserInfo, PlatformBase, ProfileInfo

BROWSER_BUNDLES = {
    "chrome": {
        "name": "Google Chrome",
        "bundle_id": "com.google.Chrome",
        "paths": [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ],
        "incognito_flag": "--incognito",
        "profile_flag": "--profile-directory",
        "profile_base": Path.home() / "Library/Application Support/Google/Chrome",
    },
    "safari": {
        "name": "Safari",
        "bundle_id": "com.apple.Safari",
        "paths": ["/Applications/Safari.app/Contents/MacOS/Safari"],
        "incognito_flag": "",
        "profile_flag": "",
        "profile_base": None,
    },
    "edge": {
        "name": "Microsoft Edge",
        "bundle_id": "com.microsoft.edgemac",
        "paths": [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ],
        "incognito_flag": "--inprivate",
        "profile_flag": "--profile-directory",
        "profile_base": Path.home() / "Library/Application Support/Microsoft Edge",
    },
    "firefox": {
        "name": "Firefox",
        "bundle_id": "org.mozilla.firefox",
        "paths": ["/Applications/Firefox.app/Contents/MacOS/firefox"],
        "incognito_flag": "--private-window",
        "profile_flag": "-P",
        "profile_base": Path.home() / "Library/Application Support/Firefox/Profiles",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "bundle_id": "com.duckduckgo.macos.browser",
        "paths": ["/Applications/DuckDuckGo.app/Contents/MacOS/DuckDuckGo"],
        "incognito_flag": "",
        "profile_flag": "",
        "profile_base": None,
    },
    "brave": {
        "name": "Brave Browser",
        "bundle_id": "com.brave.Browser",
        "paths": ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"],
        "incognito_flag": "--incognito",
        "profile_flag": "--profile-directory",
        "profile_base": Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser",
    },
}


class PlatformMacOS(PlatformBase):
    def data_dir(self) -> Path:
        d = Path.home() / ".local" / "bifrost"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def log_dir(self) -> Path:
        d = self.data_dir() / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def discover_browsers(self) -> list[BrowserInfo]:
        found = []
        for browser_type, info in BROWSER_BUNDLES.items():
            for path in info["paths"]:
                if Path(path).exists():
                    found.append(
                        BrowserInfo(
                            name=info["name"],
                            browser_type=browser_type,
                            executable=str(path),
                            platform="macos",
                            incognito_flag=info["incognito_flag"],
                            profile_flag=info["profile_flag"],
                        )
                    )
                    break
        return found

    def discover_profiles(self, browser: BrowserInfo) -> list[ProfileInfo]:
        profiles = []
        info = BROWSER_BUNDLES.get(browser.browser_type)
        if not info or not info["profile_base"]:
            return profiles

        base = Path(info["profile_base"])

        if browser.browser_type == "firefox":
            return self._discover_firefox_profiles(base, browser.browser_type)

        # Chromium-based: scan Default/ and Profile N/ directories
        for candidate in sorted(base.iterdir()) if base.exists() else []:
            if not candidate.is_dir():
                continue
            if candidate.name == "Default" or candidate.name.startswith("Profile "):
                prefs_file = candidate / "Preferences"
                display_name = candidate.name
                if prefs_file.exists():
                    try:
                        with open(prefs_file, encoding="utf-8") as f:
                            prefs = json.load(f)
                        name = prefs.get("profile", {}).get("name", "")
                        if name and name not in ("Person 1", ""):
                            display_name = name
                    except (json.JSONDecodeError, OSError):
                        pass
                profiles.append(
                    ProfileInfo(
                        name=display_name,
                        directory=candidate.name,
                        browser_type=browser.browser_type,
                    )
                )
        return profiles

    def _discover_firefox_profiles(
        self, base: Path, browser_type: str
    ) -> list[ProfileInfo]:
        profiles = []
        profiles_ini = base.parent / "profiles.ini"
        if not profiles_ini.exists():
            return profiles

        import configparser

        config = configparser.ConfigParser()
        config.read(profiles_ini)

        for section in config.sections():
            if section.startswith("Profile"):
                name = config.get(section, "Name", fallback=section)
                path = config.get(section, "Path", fallback="")
                if name and path:
                    profiles.append(
                        ProfileInfo(name=name, directory=path, browser_type=browser_type)
                    )
        return profiles

    def register_handler(self, bundle_path: str) -> bool:
        try:
            # Store current handler before overwriting
            current = self.get_current_handler()
            if current:
                prev_file = self.data_dir() / "previous_handler.txt"
                prev_file.write_text(current, encoding="utf-8")

            result = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-c",
                    (
                        "from Foundation import NSBundle; "
                        "from LaunchServices import LSSetDefaultHandlerForURLScheme; "
                        f"r1 = LSSetDefaultHandlerForURLScheme('http', '{bundle_path}'); "
                        f"r2 = LSSetDefaultHandlerForURLScheme('https', '{bundle_path}'); "
                        "print(f'{r1},{r2}')"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return "0,0" in result.stdout
        except (subprocess.SubprocessError, OSError):
            return False

    def unregister_handler(self) -> bool:
        prev_file = self.data_dir() / "previous_handler.txt"
        if not prev_file.exists():
            return False
        previous = prev_file.read_text(encoding="utf-8").strip()
        if not previous:
            return False
        return self.register_handler(previous)

    def get_current_handler(self) -> str | None:
        try:
            result = subprocess.run(
                [
                    "/usr/bin/python3",
                    "-c",
                    (
                        "from LaunchServices import LSCopyDefaultHandlerForURLScheme; "
                        "h = LSCopyDefaultHandlerForURLScheme('http'); "
                        "print(h or '')"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            handler = result.stdout.strip()
            return handler if handler else None
        except (subprocess.SubprocessError, OSError):
            return None

    def launch_browser(
        self,
        executable: str,
        url: str,
        profile_dir: str | None = None,
        profile_flag: str | None = None,
        incognito: bool = False,
        incognito_flag: str | None = None,
    ) -> None:
        # On macOS, use `open -na` to handle existing browser sessions correctly.
        # Direct executable calls lose --profile-directory when Chrome is already running.
        app_path = self._executable_to_app_path(executable)
        args = []
        if profile_dir and profile_flag:
            args.append(f"{profile_flag}={profile_dir}")
        if incognito and incognito_flag:
            args.append(incognito_flag)
        args.append(url)

        cmd = ["/usr/bin/open", "-na", app_path, "--args"] + args
        subprocess.Popen(cmd, start_new_session=True)

    @staticmethod
    def _executable_to_app_path(executable: str) -> str:
        """Convert an executable path to its .app bundle path.

        e.g. /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
           → /Applications/Google Chrome.app
        """
        parts = Path(executable).parts
        for i, part in enumerate(parts):
            if part.endswith(".app"):
                return str(Path(*parts[: i + 1]))
        return executable

    def open_default_browser(self, url: str) -> None:
        subprocess.Popen(["/usr/bin/open", url], start_new_session=True)
