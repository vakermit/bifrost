# Bifrost

**Cross-platform URL handler that routes links to the right browser and profile.**

Bifrost intercepts HTTP/HTTPS link clicks at the OS level and routes them to the correct browser and profile based on configurable rules. Like a rainbow bridge between you and your browsers.

> **Status:** Early development (v0.1.0). Works on macOS; Windows support is architecturally complete but untested on real hardware. Contributions welcome.

## Features

- **Rule-based routing** — Domain patterns and regex rules matched in priority order
- **Profile support** — Route to specific browser profiles (e.g., work Chrome vs personal Chrome)
- **Picker window** — When no rule matches, choose a browser with an option to remember
- **System tray** — Quiet menubar/tray presence with preferences access
- **Cross-platform** — macOS and Windows support from a single Python codebase
- **CLI-first** — Full management via `bifrost` command; GUI is convenience, not capability
- **Privacy-focused** — Log URLs are truncated and query strings redacted by default
- **Native UI** — [Toga](https://toga.beeware.org/) for platform-native widgets (Cocoa on macOS, WinForms on Windows)

## Quick Start

```bash
# Install (requires Python 3.11+)
pip install -e .

# Discover installed browsers and profiles
bifrost discover

# List what was found
bifrost browser list
bifrost browser profiles chrome

# Add routing rules
bifrost rule add --pattern "*.github.com" --browser chrome --profile "Work"
bifrost rule add --regex "^https://mail\." --browser chrome --profile "Personal"
bifrost rule add --pattern "*.example.com" --browser firefox --incognito

# Register as system URL handler
bifrost install

# Run the system tray app
bifrost tray

# View status
bifrost status
```

## How It Works

1. **Install** — Bifrost registers as the default HTTP/HTTPS handler on your OS
2. **Click a link** — Any app sends the URL to Bifrost instead of a browser
3. **Match** — Bifrost checks your rules in priority order for a domain or regex match
4. **Route** — The matched browser (and profile) opens with the URL
5. **No match?** — A native picker window lets you choose and optionally remember

## CLI Reference

| Command | Description |
|---------|-------------|
| `bifrost discover` | Scan for installed browsers and profiles |
| `bifrost install` / `uninstall` | Register/unregister as system URL handler |
| `bifrost browser list` | Show registered browsers |
| `bifrost browser profiles <name>` | Show profiles for a browser |
| `bifrost browser remove <name>` | Remove a browser from the database |
| `bifrost rule add` | Add a routing rule (see `--help` for options) |
| `bifrost rule list` | Show all rules in priority order |
| `bifrost rule remove <id>` | Delete a rule |
| `bifrost rule reorder <id> -p <n>` | Change a rule's priority |
| `bifrost group create <name>` | Create a rule group |
| `bifrost group list` | Show all groups |
| `bifrost config <key> [value]` | Get or set config (e.g., `default_action`, `default_browser`) |
| `bifrost status` | Show current status |
| `bifrost tray` | Run the system tray app |
| `bifrost handle <url>` | Process a URL (used internally by the OS handler) |

## Architecture

```
bifrost/
├── cli.py              # Typer CLI — primary management interface
├── db.py               # SQLite database (WAL mode)
├── rules.py            # Rule matching engine
├── handler.py          # URL routing processor
├── picker.py           # Toga native picker window
├── tray.py             # Toga StatusIcon system tray
├── security.py         # URL validation, regex safety
├── logging_config.py   # Secure log rotation
├── platform.py         # Platform detection
├── platform_base.py    # ABC interface
├── platform_macos.py   # macOS: PyObjC, Launch Services
└── platform_windows.py # Windows: registry
```

## Data Storage

| Platform | Location |
|----------|----------|
| macOS | `~/.local/bifrost/` |
| Windows | `%LOCALAPPDATA%\bifrost\` |

All data in SQLite (`bifrost.db`). Logs rotate daily with gzip compression.

## Security

- Only `http://` and `https://` URLs are accepted — all other schemes (`javascript:`, `data:`, `file:`, `ms-msdt:`) are blocked at the entry point
- Regex rules are validated at creation time — patterns with nested quantifiers (ReDoS risk) are rejected
- Browser launch uses `subprocess` with argument lists, never shell interpolation
- Log entries truncate URLs at 512 characters and redact query strings by default
- Log files are created with owner-only permissions (`0600`)

## Packaging

Bifrost uses [BeeWare Briefcase](https://briefcase.beeware.org/) for native packaging:

```bash
# Development
pip install -e ".[dev]"

# Package for macOS (.app bundle with code signing + notarization)
briefcase package macOS

# Package for Windows (.msi installer)
briefcase package windows
```

Briefcase handles code signing, notarization (macOS), and MSI generation (Windows)
from a single `pyproject.toml` configuration.

## Disclaimer

This software is provided "as is", without warranty of any kind. See the [LICENSE](LICENSE) file for details. Use at your own risk — Bifrost modifies your system's default URL handler, which affects how all applications open links. The authors are not responsible for any issues arising from its use, including but not limited to broken link handling, data loss, or security vulnerabilities.

## Contributing

Contributions are welcome. Please open an issue to discuss before submitting a PR.

## License

[MIT](LICENSE)
