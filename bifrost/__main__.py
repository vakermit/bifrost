"""Entry point for Briefcase-packaged Bifrost app.

When launched as a .app bundle, Bifrost runs the system tray with URL handler.
When launched from CLI, the typer app handles commands.
"""

import sys


def main():
    if len(sys.argv) > 1:
        from bifrost.cli import app

        app()
    else:
        from bifrost.tray import run_tray

        run_tray()


if __name__ == "__main__":
    main()
