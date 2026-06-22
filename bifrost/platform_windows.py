"""Windows platform implementation for Bifrost."""

import json
import subprocess
import sys
from pathlib import Path

from bifrost.platform_base import BrowserInfo, PlatformBase, ProfileInfo

BROWSER_REGISTRY = {
    "chrome": {
        "name": "Google Chrome",
        "registry_key": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        "default_paths": [
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        ],
        "incognito_flag": "--incognito",
        "profile_flag": "--profile-directory",
        "profile_base": Path.home() / "AppData/Local/Google/Chrome/User Data",
    },
    "edge": {
        "name": "Microsoft Edge",
        "registry_key": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe",
        "default_paths": [
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        ],
        "incognito_flag": "--inprivate",
        "profile_flag": "--profile-directory",
        "profile_base": Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    },
    "firefox": {
        "name": "Firefox",
        "registry_key": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe",
        "default_paths": [
            Path("C:/Program Files/Mozilla Firefox/firefox.exe"),
            Path("C:/Program Files (x86)/Mozilla Firefox/firefox.exe"),
        ],
        "incognito_flag": "--private-window",
        "profile_flag": "-P",
        "profile_base": Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles",
    },
    "brave": {
        "name": "Brave Browser",
        "registry_key": r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe",
        "default_paths": [
            Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/Application/brave.exe",
            Path("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"),
        ],
        "incognito_flag": "--incognito",
        "profile_flag": "--profile-directory",
        "profile_base": Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data",
    },
    "duckduckgo": {
        "name": "DuckDuckGo",
        "registry_key": "",
        "default_paths": [
            Path.home() / "AppData/Local/DuckDuckGo/DuckDuckGo.exe",
        ],
        "incognito_flag": "",
        "profile_flag": "",
        "profile_base": None,
    },
}


class PlatformWindows(PlatformBase):
    def data_dir(self) -> Path:
        import platformdirs

        d = Path(platformdirs.user_data_dir("bifrost", appauthor=False))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def log_dir(self) -> Path:
        d = self.data_dir() / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def discover_browsers(self) -> list[BrowserInfo]:
        found = []
        for browser_type, info in BROWSER_REGISTRY.items():
            exe_path = self._find_browser_exe(info)
            if exe_path:
                found.append(
                    BrowserInfo(
                        name=info["name"],
                        browser_type=browser_type,
                        executable=str(exe_path),
                        platform="windows",
                        incognito_flag=info["incognito_flag"],
                        profile_flag=info["profile_flag"],
                    )
                )
        return found

    def _find_browser_exe(self, info: dict) -> Path | None:
        # Try registry first
        if info["registry_key"] and sys.platform == "win32":
            try:
                import winreg

                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, info["registry_key"]) as key:
                    exe_path = Path(winreg.QueryValue(key, None))
                    if exe_path.exists():
                        return exe_path
            except (OSError, ImportError):
                pass

        # Fall back to known paths
        for path in info["default_paths"]:
            if path.exists():
                return path

        return None

    def discover_profiles(self, browser: BrowserInfo) -> list[ProfileInfo]:
        profiles = []
        info = BROWSER_REGISTRY.get(browser.browser_type)
        if not info or not info["profile_base"]:
            return profiles

        base = Path(info["profile_base"])

        if browser.browser_type == "firefox":
            return self._discover_firefox_profiles(base, browser.browser_type)

        # Chromium-based
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
        if sys.platform != "win32":
            return False
        try:
            import winreg

            # Register BifrostURL ProgId
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\BifrostURL") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Bifrost URL Handler")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

            cmd = f'"{bundle_path}" "%1"'
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER, r"Software\Classes\BifrostURL\shell\open\command"
            ) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, cmd)

            # Store previous handler
            current = self.get_current_handler()
            if current:
                prev_file = self.data_dir() / "previous_handler.txt"
                prev_file.write_text(current, encoding="utf-8")

            return True
        except (OSError, ImportError):
            return False

    def unregister_handler(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg

            winreg.DeleteKey(
                winreg.HKEY_CURRENT_USER, r"Software\Classes\BifrostURL\shell\open\command"
            )
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\BifrostURL\shell\open")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\BifrostURL\shell")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\BifrostURL")
            return True
        except (OSError, ImportError):
            return False

    def get_current_handler(self) -> str | None:
        if sys.platform != "win32":
            return None
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
            ) as key:
                prog_id, _ = winreg.QueryValueEx(key, "ProgId")
                return prog_id
        except (OSError, ImportError):
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
        cmd = [executable]
        if profile_dir and profile_flag:
            cmd.extend([profile_flag, profile_dir])
        if incognito and incognito_flag:
            cmd.append(incognito_flag)
        cmd.append(url)
        subprocess.Popen(cmd, creationflags=0x00000008)  # DETACHED_PROCESS

    def open_default_browser(self, url: str) -> None:
        import os

        os.startfile(url)
