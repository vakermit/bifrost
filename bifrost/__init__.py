"""Bifrost — cross-platform URL handler that routes links to the right browser and profile."""

__version__ = "0.1.0"


def main():
    """Entry point for Briefcase-packaged app. Launches tray with URL handler."""
    from bifrost.tray import run_tray

    run_tray()
