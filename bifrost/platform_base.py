"""Platform abstraction interface for Bifrost."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BrowserInfo:
    name: str
    browser_type: str  # chrome, safari, edge, firefox, duckduckgo, brave, other
    executable: str
    platform: str  # macos, windows
    incognito_flag: str = ""
    profile_flag: str = ""


@dataclass
class ProfileInfo:
    name: str
    directory: str
    browser_type: str


class PlatformBase(ABC):
    @abstractmethod
    def data_dir(self) -> Path:
        """Return the platform-specific data directory for Bifrost."""

    @abstractmethod
    def log_dir(self) -> Path:
        """Return the platform-specific log directory."""

    @abstractmethod
    def discover_browsers(self) -> list[BrowserInfo]:
        """Discover installed browsers on this platform."""

    @abstractmethod
    def discover_profiles(self, browser: BrowserInfo) -> list[ProfileInfo]:
        """Discover profiles for a given browser."""

    @abstractmethod
    def register_handler(self, bundle_path: str) -> bool:
        """Register Bifrost as the system URL handler."""

    @abstractmethod
    def unregister_handler(self) -> bool:
        """Restore the previous default URL handler."""

    @abstractmethod
    def get_current_handler(self) -> str | None:
        """Return the current default URL handler identifier."""

    @abstractmethod
    def launch_browser(
        self,
        executable: str,
        url: str,
        profile_dir: str | None = None,
        profile_flag: str | None = None,
        incognito: bool = False,
        incognito_flag: str | None = None,
    ) -> None:
        """Launch a browser with the given URL and optional profile/incognito flags."""

    @abstractmethod
    def open_default_browser(self, url: str) -> None:
        """Open a URL in the system default browser (fallback)."""

    def db_path(self) -> Path:
        return self.data_dir() / "bifrost.db"

    def dead_letter_path(self) -> Path:
        return self.data_dir() / "dead_letters.txt"

    def socket_path(self) -> Path:
        return self.data_dir() / "bifrost.sock"
