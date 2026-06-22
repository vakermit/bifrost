---
task: "Design and build Bifrost cross-platform browser routing handler"
project: bifrost
effort: deep
effort_source: classifier
phase: complete
progress: 0/55
mode: interactive
started: 2026-06-22T16:00:00Z
updated: 2026-06-22T16:20:00Z
---

## Problem

Every link click on macOS and Windows goes to a single default browser. Power users with multiple browsers and multiple profiles — work Chrome, personal Chrome, Safari for banking, DuckDuckGo for privacy — have no way to route URLs intelligently. The only options are manual copy-paste into the right browser or third-party apps that are either abandoned, closed-source, or lack profile-level routing. There is no open-source, cross-platform, rule-based HTTP/HTTPS handler that supports browser profiles, regex pattern matching, grouped rules, and a GUI picker fallback.

## Vision

Click a link in Slack, and it opens in the correct Chrome work profile. Click a personal link in Messages or a Windows app, and it opens in the right browser. Click an unknown link, and a clean picker window appears showing the URL, letting you choose a browser and profile, with an option to remember that choice as an exact URL, domain, or custom regex — editable on the spot. The system tray/menubar icon glows quietly, and a `bifrost` CLI lets you manage everything from the terminal. The whole system is open-source, PII-free, cross-platform (macOS + Windows), and installable with a single command.

## Out of Scope

- **Linux support.** macOS and Windows only in v1; XDG handler registration is a different system.
- **Browser extension integration.** Bifrost operates at the OS URL-scheme level, not inside browsers.
- **URL rewriting or proxying.** Bifrost routes URLs; it does not modify, filter, or proxy them.
- **Site safety / threat intelligence.** Noted as future consideration; not v1.
- **Automatic rule generation from browsing history.** Rules are user-defined only.
- **Sync across machines.** Local-only data store.

## Principles

- A URL handler must be invisible when working correctly and obvious when it needs input.
- CLI-first: every operation the menubar can do, the CLI can do. The GUI is convenience, not capability.
- Rules are data, not code. A non-developer should be able to understand and edit them.
- Open-source means PII-free from day one — no names, companies, or personal data in code, comments, commit messages, or test fixtures.
- Browser and profile discovery is expensive; cache it and refresh on demand.
- Platform-specific code lives in platform modules; the core (rules, discovery logic, database, CLI) is pure Python that runs identically on macOS and Windows.

## Constraints

- **Pure Python architecture** — no Swift, no Xcode. Single codebase for both platforms.
- Python 3.11+ with Typer for the CLI. The CLI is the primary management interface and is cross-platform.
- **Packaging:** BeeWare Briefcase for cross-platform packaging — produces signed/notarized `.app` bundles on macOS and `.msi` installers on Windows from a single `pyproject.toml` config. Replaces py2app + PyInstaller.
- **macOS:** Briefcase creates the `.app` bundle with `Info.plist` `CFBundleURLTypes` for URL scheme registration. PyObjC handles Apple Events (`kAEGetURL`) for URL dispatch. Toga provides the menubar StatusIcon.
- **Windows:** URL protocol handler registration via the Windows Registry (`HKCU\Software\Classes`). Briefcase packages as `.msi` installer. Toga provides the system tray StatusIcon.
- **GUI:** Toga (BeeWare) for picker window and system tray — native widgets on every platform (Cocoa on macOS, WinForms on Windows). No tkinter, no pywebview — native look and feel with no embedded browser attack surface.
- SQLite database at `~/.local/bifrost/bifrost.db` (macOS) or `%LOCALAPPDATA%\bifrost\bifrost.db` (Windows) for rules, groups, browsers, and profiles. WAL mode for concurrent CLI + handler access.
- Logs at `~/.local/bifrost/logs/` (macOS) or `%LOCALAPPDATA%\bifrost\logs\` (Windows) with rotation (keep 7 days, compress older). URLs truncated at 512 chars by default; query strings redacted unless opt-in.
- **Security:** Only `http://` and `https://` schemes accepted at the handler entry point. All other schemes (`javascript:`, `data:`, `file:`) rejected before rule matching, logging, or browser launch. Regex rules validated at creation time; nested quantifiers rejected to prevent ReDoS.
- The rule engine, browser discovery, and database layer are pure Python — shared across platforms. Only the URL handler registration and OS-specific paths have platform-specific implementations behind an ABC interface.
- No PII in the repository: no real names, no company names, no real email addresses in any file including tests and examples.

## Goal

Build Bifrost — an open-source, pure-Python, cross-platform (macOS + Windows) HTTP/HTTPS URL handler with three components: (1) a Python Typer CLI for installation, browser/profile discovery, rule and group management, and logging; (2) a Python routing processor packaged as a macOS `.app` bundle (via py2app/PyObjC) or Windows `.exe` (via PyInstaller) that registers as the system URL handler, validates incoming URLs against security rules, matches them against an ordered rule database, and routes to the correct browser/profile; and (3) a pystray system tray/menubar presence with a tkinter picker window for unmatched URLs with a "remember" feature offering exact-URL, domain, or custom-regex persistence.

## Criteria

### System Registration (macOS)

- [ ] ISC-1: `bifrost install` on macOS registers Bifrost as the default HTTP handler via `LSSetDefaultHandlerForURLScheme`
- [ ] ISC-2: `bifrost install` on macOS registers Bifrost as the default HTTPS handler via `LSSetDefaultHandlerForURLScheme`
- [ ] ISC-3: `bifrost uninstall` on macOS restores the previous default browser for both HTTP and HTTPS schemes
- [ ] ISC-4: After install on macOS, clicking an `http://` link in any app opens the Bifrost routing processor

### System Registration (Windows)

- [ ] ISC-39: `bifrost install` on Windows writes `HKCU\Software\Classes\BifrostURL` registry key with the handler command
- [ ] ISC-40: `bifrost install` on Windows sets Bifrost as the default HTTP protocol handler via registry
- [ ] ISC-41: `bifrost install` on Windows sets Bifrost as the default HTTPS protocol handler via registry
- [ ] ISC-42: `bifrost uninstall` on Windows removes Bifrost registry keys and restores the previous default
- [ ] ISC-43: After install on Windows, clicking an `http://` link in any app opens the Bifrost routing processor

### Browser & Profile Discovery

- [ ] ISC-5: `bifrost discover` on macOS detects Chrome if installed (via `/Applications/`) and stores it in SQLite with its executable path
- [ ] ISC-6: `bifrost discover` on macOS detects Safari if installed and stores it in SQLite
- [ ] ISC-7: `bifrost discover` detects Edge if installed and stores it in SQLite (both platforms)
- [ ] ISC-8: `bifrost discover` detects DuckDuckGo Browser if installed and stores it in SQLite (both platforms)
- [ ] ISC-9: `bifrost discover` detects Firefox if installed and stores it in SQLite (both platforms)
- [ ] ISC-10: `bifrost discover` auto-scans Chrome profiles and stores them by display name (e.g., "Personal", "RYN", not "Profile 3")
- [ ] ISC-11: `bifrost discover` auto-scans Edge profiles and stores them by display name
- [ ] ISC-12: `bifrost discover` auto-scans Firefox profiles and stores them by display name
- [ ] ISC-13: Browser and profile records persist in SQLite across CLI invocations
- [ ] ISC-53: `bifrost browser list` displays all registered browsers with name, platform, executable path, and profile count
- [ ] ISC-54: `bifrost browser profiles <name>` displays all profiles for the named browser with display name and directory
- [ ] ISC-55: `bifrost browser remove <name>` removes a browser and its profiles from SQLite
- [ ] ISC-44: `bifrost discover` on Windows detects Chrome via registry (`HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths`) or `Program Files`
- [ ] ISC-45: `bifrost discover` on Windows detects Brave if installed and stores it in SQLite
- [ ] ISC-46: Browser discovery uses platform-appropriate paths (`/Applications/` on macOS, `Program Files` + registry on Windows)

### Rule & Group Management

- [ ] ISC-14: `bifrost rule add --pattern "*.example.com" --browser chrome --profile "Work"` creates a domain rule in SQLite
- [ ] ISC-15: `bifrost rule add --regex "^https://jira\." --browser chrome --profile "Work"` creates a regex rule in SQLite
- [ ] ISC-16: `bifrost rule list` displays all rules in priority order with group, pattern, browser, profile, and incognito flag
- [ ] ISC-17: `bifrost rule remove <id>` deletes a rule from SQLite
- [ ] ISC-18: `bifrost rule reorder <id> --position <n>` changes rule priority
- [ ] ISC-19: `bifrost group create <name>` creates a named group in SQLite
- [ ] ISC-20: `bifrost group list` displays all groups with their rule count
- [ ] ISC-21: Rules can be assigned to a group via `--group <name>` on creation
- [ ] ISC-22: Rules and groups support optional user-defined names via `--name <label>`
- [ ] ISC-23: A rule can specify `--incognito` to open in private/incognito mode

### URL Routing Processor

- [ ] ISC-24: When the routing processor receives a URL, it queries rules from SQLite in priority order and stops at the first match
- [ ] ISC-25: A matched rule launches the specified browser with the correct `--profile-directory` flag and the URL
- [ ] ISC-26: A matched rule with `--incognito` launches the browser with the appropriate private-mode flag (`--incognito` for Chrome, `--private-window` for Firefox, etc.)
- [ ] ISC-27: When no rule matches and default behavior is a specific browser/profile, that browser/profile opens
- [ ] ISC-28: When no rule matches and default behavior is "ask", the picker window appears

### Picker Window

- [ ] ISC-29: The picker window displays the full URL with a copy-to-clipboard button
- [ ] ISC-30: The picker window shows all discovered browsers and their profiles as selectable options
- [ ] ISC-31: The picker window has a "Remember" checkbox with a dropdown: "This exact URL", "This domain", or "Custom regex"
- [ ] ISC-32: Selecting "Custom regex" shows an editable text field pre-populated with a domain-based regex
- [ ] ISC-33: Clicking "Open" in the picker launches the selected browser/profile and, if "Remember" is checked, persists the rule to SQLite

### System Tray / Menubar App

- [ ] ISC-34: On macOS, the menubar icon is visible in the menu bar when Bifrost is running
- [ ] ISC-35: The menubar/tray dropdown shows a "Preferences" option that opens a rule-editing interface
- [ ] ISC-47: On Windows, the system tray icon is visible in the notification area when Bifrost is running
- [ ] ISC-48: On Windows, right-clicking the tray icon shows "Preferences" and "Exit" options

### Logging

- [ ] ISC-36: Every URL routing event is logged to `~/.local/bifrost/logs/bifrost.log` with timestamp, URL, matched rule (or "picker"), and target browser/profile
- [ ] ISC-37: Logs rotate daily; files older than 7 days are gzip-compressed; files older than 30 days are deleted

### Cross-Platform Data

- [ ] ISC-49: On macOS, data directory resolves to `~/.local/bifrost/`
- [ ] ISC-50: On Windows, data directory resolves to `%LOCALAPPDATA%\bifrost\`
- [ ] ISC-51: The picker window renders and functions correctly on both macOS and Windows

### Security (RedTeam-derived)

- [ ] ISC-56: Handler rejects URLs with schemes other than `http://` and `https://` before any processing (blocks `javascript:`, `data:`, `file:`, `ms-msdt:`)
- [ ] ISC-57: Regex rules are validated at creation time — patterns with nested quantifiers (`(a+)+`, `(.*)+`) are rejected
- [ ] ISC-58: Browser launch uses `subprocess` with argument list (not shell=True) and validates URL scheme before passing to subprocess
- [ ] ISC-59: Log entries truncate URLs at 512 characters by default; query strings are redacted unless `--verbose-log` is enabled
- [ ] ISC-60: Log files are created with `0600` (owner-only) permissions on macOS and equivalent ACL on Windows
- [ ] ISC-61: On startup, handler verifies it is still the registered URL handler and alerts the user if another app has taken over
- [ ] ISC-62: Handler captures the raw URL as its first action before any DB or rule processing — if it crashes, the URL is recoverable
- [ ] ISC-63: If handler crashes 3 times in 60 seconds, it writes URLs to a dead-letter file and falls back to system default browser via `NSWorkspace.shared.open()` (macOS) or `ShellExecute` (Windows)

### Anti-criteria

- [ ] ISC-38: Anti: No file in the repository contains PII — no real person names, company names, or email addresses in source code, tests, comments, or documentation
- [ ] ISC-52: Anti: No platform-specific code exists outside clearly named platform modules (e.g., `platform_macos.py`, `platform_windows.py`)
- [ ] ISC-64: Anti: Handler never passes a non-http/https URL to subprocess — no protocol smuggling to browser
- [ ] ISC-65: Anti: No user-supplied regex is evaluated without a compilation timeout or complexity check

## Test Strategy

| ISC | Type | Check | Threshold | Tool |
|-----|------|-------|-----------|------|
| ISC-1 | integration | Run `bifrost install`, then query `LSCopyDefaultHandlerForURLScheme("http")` | Returns Bifrost bundle ID | Bash + Swift helper |
| ISC-2 | integration | Same as ISC-1 for "https" | Returns Bifrost bundle ID | Bash + Swift helper |
| ISC-3 | integration | Run `bifrost uninstall`, re-query default handler | Returns previous browser bundle ID | Bash + Swift helper |
| ISC-4 | integration | `open http://example.com` after install | Bifrost processor activates | Bash |
| ISC-5–9 | unit | Run `bifrost discover`, query SQLite for browser records | Each installed browser has a row | Bash + sqlite3 |
| ISC-10–12 | unit | Run `bifrost discover`, query SQLite for profile records by display name | Profile names match `Preferences` JSON | Bash + sqlite3 |
| ISC-13 | unit | Run discover twice; second run reads from DB | Rows persist | sqlite3 |
| ISC-14–15 | unit | Run rule add, query SQLite | Row exists with correct pattern and type | Bash + sqlite3 |
| ISC-16 | unit | Run `bifrost rule list` | Output contains all rules in order | Bash |
| ISC-17 | unit | Run rule remove, query SQLite | Row absent | Bash + sqlite3 |
| ISC-18 | unit | Run reorder, query SQLite `ORDER BY priority` | Order updated | sqlite3 |
| ISC-19–23 | unit | Run group/rule commands with flags, query SQLite | Correct fields stored | Bash + sqlite3 |
| ISC-24 | integration | Insert two rules, send URL matching rule 2 | Rule 2 match logged, not rule 1 | Log inspection |
| ISC-25 | integration | Insert rule for Chrome "Work" profile, trigger URL | Chrome launches with `--profile-directory` | Process inspection |
| ISC-26 | integration | Insert incognito rule, trigger URL | Browser launches with incognito flag | Process inspection |
| ISC-27 | integration | Set default to Safari, trigger unmatched URL | Safari opens | Process inspection |
| ISC-28 | integration | Set default to "ask", trigger unmatched URL | Picker window appears | Visual / Interceptor |
| ISC-29 | visual | Open picker, check URL display and copy button | URL shown, clipboard populated on click | Interceptor |
| ISC-30 | visual | Open picker with multiple browsers discovered | All browsers/profiles listed | Interceptor |
| ISC-31–33 | integration | Use picker with Remember checked, verify rule in SQLite | New rule row exists | sqlite3 |
| ISC-34 | visual | Launch Bifrost, check menu bar | Icon visible | Screenshot |
| ISC-35 | visual | Click menubar → Preferences | Rule editor opens | Interceptor |
| ISC-36 | unit | Trigger a routing event, read log file | Log entry with timestamp, URL, rule, target | Bash + Read |
| ISC-37 | unit | Create logs older than 7 and 30 days, trigger rotation | 7-day compressed, 30-day deleted | Bash + ls |
| ISC-38 | scan | `rg -i` with PII patterns against all repo files | Zero matches outside ISA scan command | Bash + rg |
| ISC-39–41 | integration | Run `bifrost install` on Windows, query registry for protocol handlers | Bifrost keys present | PowerShell + reg query |
| ISC-42 | integration | Run `bifrost uninstall` on Windows, query registry | Bifrost keys absent | PowerShell + reg query |
| ISC-43 | integration | Click `http://` link on Windows after install | Bifrost activates | Manual / PowerShell |
| ISC-44–46 | unit | Run `bifrost discover` on Windows, query SQLite | Browser rows with correct Windows paths | Bash + sqlite3 |
| ISC-47–48 | visual | Launch Bifrost on Windows, check system tray | Icon visible, right-click menu works | Screenshot |
| ISC-49–50 | unit | Check data dir path on each platform | Correct OS-specific path | Bash / PowerShell |
| ISC-51 | visual | Open picker on both platforms | Renders correctly on both | Screenshot |
| ISC-52 | scan | `rg -l "import.*platform" --glob "!platform_*.py"` in core modules | Zero matches of raw platform calls outside platform modules | Bash + rg |
| ISC-53 | unit | Run `bifrost browser list` after discovery | Table shows all browsers with name, platform, path, profile count | Bash |
| ISC-54 | unit | Run `bifrost browser profiles chrome` | Table shows all Chrome profiles by display name | Bash |
| ISC-55 | unit | Run `bifrost browser remove <name>`, query SQLite | Browser and profile rows absent | Bash + sqlite3 |

## Features

| Name | Description | Satisfies | Depends On | Parallelizable |
|------|-------------|-----------|------------|----------------|
| platform-abstraction | Platform module pattern: `platform_macos.py`, `platform_windows.py` with shared interface for paths, registration, tray, picker | ISC-46, ISC-49–50, ISC-52 | — | yes |
| swift-app-bundle | macOS app bundle with URL scheme handler, routing processor, menubar NSStatusItem, and SwiftUI picker window | ISC-1–4, ISC-24–28, ISC-34 | platform-abstraction | yes |
| windows-handler | Windows registry-based URL handler, Python routing processor, system tray (pystray/tkinter), and tkinter picker window | ISC-39–43, ISC-47–48, ISC-51 | platform-abstraction | yes |
| python-cli | Typer CLI for install/uninstall, discover, rule/group CRUD, log viewing | ISC-1–3, ISC-5–23, ISC-36–37, ISC-39–42 | platform-abstraction | yes |
| sqlite-schema | Database schema for browsers, profiles, rules, groups, config | ISC-13–23, ISC-24, ISC-33 | — | yes |
| browser-discovery | Detection and profile scanning for Chrome, Safari, Edge, Firefox, DuckDuckGo, Brave — platform-aware paths | ISC-5–12, ISC-44–46 | sqlite-schema, platform-abstraction | no |
| rule-engine | Ordered rule matching: regex and domain patterns, group support, incognito flag | ISC-14–18, ISC-21–26 | sqlite-schema | no |
| picker-window | Cross-platform picker: SwiftUI on macOS, tkinter on Windows. URL display, copy button, browser/profile selector, remember options | ISC-29–33, ISC-51 | platform-abstraction, sqlite-schema | yes |
| tray-app | Cross-platform tray: NSStatusItem on macOS, pystray/tkinter on Windows | ISC-34–35, ISC-47–48 | platform-abstraction | yes |
| logging | File-based logging with daily rotation, compression, and cleanup | ISC-36–37 | platform-abstraction | yes |
| pii-guard | CI-ready scan ensuring no PII in repo | ISC-38, ISC-52 | — | yes |
