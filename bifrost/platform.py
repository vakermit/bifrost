"""Platform detection and routing."""

import sys

from bifrost.platform_base import PlatformBase


def get_platform() -> PlatformBase:
    if sys.platform == "darwin":
        from bifrost.platform_macos import PlatformMacOS

        return PlatformMacOS()
    elif sys.platform == "win32":
        from bifrost.platform_windows import PlatformWindows

        return PlatformWindows()
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")
