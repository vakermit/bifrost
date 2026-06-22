"""Bifrost CLI — Typer-based command interface."""

import sys

import typer
from rich.console import Console
from rich.table import Table

from bifrost import __version__
from bifrost.db import Database
from bifrost.logging_config import cleanup_old_logs, setup_logging
from bifrost.platform import get_platform
from bifrost.security import validate_regex

app = typer.Typer(
    name="bifrost",
    help="Cross-platform URL handler — route links to the right browser and profile.",
    no_args_is_help=True,
)
browser_app = typer.Typer(help="Manage registered browsers and profiles.")
rule_app = typer.Typer(help="Manage URL routing rules.")
group_app = typer.Typer(help="Manage rule groups.")
app.add_typer(browser_app, name="browser")
app.add_typer(rule_app, name="rule")
app.add_typer(group_app, name="group")

console = Console()


def _get_db() -> Database:
    platform = get_platform()
    return Database(platform.db_path())


# --- Top-level commands ---


@app.command()
def version():
    """Show Bifrost version."""
    console.print(f"bifrost {__version__}")


@app.command()
def install():
    """Register Bifrost as the system URL handler."""
    platform = get_platform()

    current = platform.get_current_handler()
    console.print(f"Current handler: {current or 'none'}")

    if sys.platform == "win32":
        # Windows: register ProgId and guide user to Settings
        handler_path = sys.executable
        success = platform.register_handler(handler_path)
        if success:
            console.print("[green]✓[/] BifrostURL protocol handler registered.")
            console.print()
            console.print("[yellow]Important:[/] Windows requires manual default app selection.")
            console.print("Please open: Settings → Apps → Default Apps → Choose defaults by protocol")
            console.print("Set HTTP and HTTPS to 'Bifrost URL Handler'.")
        else:
            console.print("[red]✗[/] Failed to register handler.")
            raise typer.Exit(1)
    else:
        # macOS: register via Launch Services
        from pathlib import Path

        bundle_id = "org.bifrost.bifrost"
        app_path = Path("/Applications/Bifrost.app")

        if not app_path.exists():
            console.print("[red]✗[/] Bifrost.app not found in /Applications/")
            console.print("Build and install first:")
            console.print("  briefcase build macOS app")
            console.print("  cp -r build/bifrost/macos/app/Bifrost.app /Applications/")
            raise typer.Exit(1)

        success = platform.register_handler(bundle_id)
        if success:
            console.print(f"[green]✓[/] Registered as default HTTP/HTTPS handler.")
        else:
            console.print("[yellow]![/] macOS requires manual confirmation on Ventura+.")

        console.print()
        console.print("To complete setup, open:")
        console.print("  [cyan]System Settings → Desktop & Dock → Default web browser[/]")
        console.print("  Select [bold]Bifrost[/] from the dropdown.")
        console.print()
        console.print("Or run:")
        console.print("  [cyan]open x-apple.systempreferences:com.apple.Desktop-Settings.extension[/]")


@app.command()
def uninstall():
    """Restore the previous default URL handler."""
    platform = get_platform()
    success = platform.unregister_handler()
    if success:
        console.print("[green]✓[/] Previous handler restored.")
    else:
        console.print("[yellow]![/] No previous handler recorded or uninstall failed.")
        console.print("You may need to set your default browser manually in System Settings.")


@app.command()
def discover():
    """Discover installed browsers and their profiles."""
    platform = get_platform()
    db = _get_db()

    console.print("Scanning for browsers...")
    browsers = platform.discover_browsers()

    if not browsers:
        console.print("[yellow]No browsers found.[/]")
        return

    for browser_info in browsers:
        browser_id = db.upsert_browser(
            name=browser_info.name,
            browser_type=browser_info.browser_type,
            executable=browser_info.executable,
            platform=browser_info.platform,
            incognito_flag=browser_info.incognito_flag,
            profile_flag=browser_info.profile_flag,
        )
        console.print(f"  [green]✓[/] {browser_info.name} ({browser_info.executable})")

        profiles = platform.discover_profiles(browser_info)
        for profile in profiles:
            db.upsert_profile(browser_id, profile.name, profile.directory)
            console.print(f"      Profile: {profile.name} ({profile.directory})")

    console.print(f"\n[green]Done.[/] Found {len(browsers)} browser(s).")


@app.command()
def tray():
    """Run the Bifrost system tray application."""
    from bifrost.tray import run_tray

    run_tray()


@app.command()
def handle(url: str):
    """Process a URL through Bifrost's rule engine (used by the OS handler)."""
    platform = get_platform()
    db = _get_db()
    logger = setup_logging(platform.log_dir())
    cleanup_old_logs(platform.log_dir())

    from bifrost.handler import handle_url

    handle_url(url, db=db)


@app.command()
def status():
    """Show Bifrost status."""
    platform = get_platform()
    db = _get_db()

    current_handler = platform.get_current_handler()
    browsers = db.list_browsers()
    rules = db.list_rules()
    default_action = db.get_config("default_action", "ask")

    table = Table(title="Bifrost Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Version", __version__)
    table.add_row("Platform", sys.platform)
    table.add_row("Data directory", str(platform.data_dir()))
    table.add_row("Current handler", current_handler or "not set")
    table.add_row("Registered browsers", str(len(browsers)))
    table.add_row("Active rules", str(len(rules)))
    table.add_row("Default action", default_action)

    console.print(table)


# --- Browser commands ---


@browser_app.command("list")
def browser_list():
    """List all registered browsers."""
    db = _get_db()
    browsers = db.list_browsers()

    if not browsers:
        console.print("No browsers registered. Run [cyan]bifrost discover[/] first.")
        return

    table = Table(title="Registered Browsers")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Platform")
    table.add_column("Executable")
    table.add_column("Profiles", justify="right")

    for b in browsers:
        table.add_row(b["name"], b["browser_type"], b["platform"],
                      b["executable"], str(b["profile_count"]))

    console.print(table)


@browser_app.command("profiles")
def browser_profiles(name: str = typer.Argument(help="Browser name or type (e.g., chrome, edge)")):
    """List profiles for a browser."""
    db = _get_db()
    browser = db.get_browser_by_name(name)

    if not browser:
        console.print(f"[red]Browser '{name}' not found.[/] Run [cyan]bifrost browser list[/].")
        raise typer.Exit(1)

    profiles = db.list_profiles(browser["id"])

    if not profiles:
        console.print(f"No profiles found for {browser['name']}.")
        return

    table = Table(title=f"Profiles — {browser['name']}")
    table.add_column("Name", style="cyan")
    table.add_column("Directory")

    for p in profiles:
        table.add_row(p["name"], p["directory"])

    console.print(table)


@browser_app.command("remove")
def browser_remove(name: str = typer.Argument(help="Browser name or type to remove")):
    """Remove a browser and its profiles from the database."""
    db = _get_db()
    if db.remove_browser(name):
        console.print(f"[green]✓[/] Removed '{name}' and its profiles.")
    else:
        console.print(f"[red]Browser '{name}' not found.[/]")
        raise typer.Exit(1)


# --- Rule commands ---


@rule_app.command("add")
def rule_add(
    browser: str = typer.Option(..., "--browser", "-b", help="Browser name or type"),
    pattern: str = typer.Option(None, "--pattern", "-p", help="Domain pattern (e.g., *.example.com)"),
    regex: str = typer.Option(None, "--regex", "-r", help="Regex pattern"),
    profile: str = typer.Option(None, "--profile", help="Profile name"),
    group: str = typer.Option(None, "--group", "-g", help="Group name"),
    incognito: bool = typer.Option(False, "--incognito", "-i", help="Open in private/incognito mode"),
    name: str = typer.Option(None, "--name", "-n", help="Optional rule name"),
):
    """Add a URL routing rule."""
    if not pattern and not regex:
        console.print("[red]Must specify --pattern or --regex[/]")
        raise typer.Exit(1)

    if pattern and regex:
        console.print("[red]Specify --pattern or --regex, not both[/]")
        raise typer.Exit(1)

    db = _get_db()

    # Resolve browser
    browser_row = db.get_browser_by_name(browser)
    if not browser_row:
        console.print(f"[red]Browser '{browser}' not found.[/] Run [cyan]bifrost discover[/] first.")
        raise typer.Exit(1)

    # Resolve profile
    profile_id = None
    if profile:
        profiles = db.list_profiles(browser_row["id"])
        matching = [p for p in profiles if p["name"].lower() == profile.lower()]
        if not matching:
            console.print(f"[red]Profile '{profile}' not found for {browser_row['name']}.[/]")
            console.print("Available profiles:")
            for p in profiles:
                console.print(f"  - {p['name']}")
            raise typer.Exit(1)
        profile_id = matching[0]["id"]

    # Resolve group
    group_id = None
    if group:
        groups = db.list_groups()
        matching = [g for g in groups if g["name"].lower() == group.lower()]
        if not matching:
            console.print(f"[red]Group '{group}' not found.[/] Create it with [cyan]bifrost group create {group}[/].")
            raise typer.Exit(1)
        group_id = matching[0]["id"]

    # Determine pattern type and validate
    if regex:
        valid, reason = validate_regex(regex)
        if not valid:
            console.print(f"[red]Invalid regex:[/] {reason}")
            raise typer.Exit(1)
        the_pattern = regex
        pattern_type = "regex"
    else:
        the_pattern = pattern
        pattern_type = "domain"

    rule_id = db.add_rule(
        pattern=the_pattern,
        pattern_type=pattern_type,
        browser_id=browser_row["id"],
        profile_id=profile_id,
        group_id=group_id,
        incognito=incognito,
        name=name,
    )
    console.print(f"[green]✓[/] Rule #{rule_id} created: {the_pattern} → {browser_row['name']}"
                  + (f" [{profile}]" if profile else "")
                  + (" [incognito]" if incognito else ""))


@rule_app.command("list")
def rule_list():
    """List all routing rules in priority order."""
    db = _get_db()
    rules = db.list_rules()

    if not rules:
        console.print("No rules defined. Add one with [cyan]bifrost rule add[/].")
        return

    table = Table(title="Routing Rules (priority order)")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Pattern")
    table.add_column("Type")
    table.add_column("Browser")
    table.add_column("Profile")
    table.add_column("Group")
    table.add_column("Incognito")

    for r in rules:
        table.add_row(
            str(r.id),
            r.name or "-",
            r.pattern,
            r.pattern_type,
            r.browser_name,
            r.profile_name or "-",
            r.group_name or "-",
            "✓" if r.incognito else "-",
        )

    console.print(table)


@rule_app.command("import")
def rule_import(
    file: str = typer.Argument(help="File to import (YAML, text with URLs, or CSV)"),
    browser: str = typer.Option(..., "--browser", "-b", help="Browser for all imported rules"),
    profile: str = typer.Option(None, "--profile", help="Profile for all imported rules"),
    group: str = typer.Option(None, "--group", "-g", help="Group name (created if missing)"),
    incognito: bool = typer.Option(False, "--incognito", "-i", help="Open in private/incognito mode"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be imported without saving"),
):
    """Import URL rules from a file.

    Supports YAML (extracts all URLs from values), plain text (one URL per line),
    or CSV (pattern,pattern_type columns). Extracts domains from URLs and creates
    domain rules for each unique host.
    """
    from pathlib import Path
    from urllib.parse import urlparse

    file_path = Path(file).expanduser()
    if not file_path.exists():
        console.print(f"[red]File not found:[/] {file_path}")
        raise typer.Exit(1)

    db = _get_db()

    # Resolve browser
    browser_row = db.get_browser_by_name(browser)
    if not browser_row:
        console.print(f"[red]Browser '{browser}' not found.[/] Run [cyan]bifrost discover[/] first.")
        raise typer.Exit(1)

    # Resolve profile
    profile_id = None
    if profile:
        profiles = db.list_profiles(browser_row["id"])
        matching = [p for p in profiles if p["name"].lower() == profile.lower()]
        if not matching:
            console.print(f"[red]Profile '{profile}' not found for {browser_row['name']}.[/]")
            raise typer.Exit(1)
        profile_id = matching[0]["id"]

    # Resolve or create group
    group_id = None
    if group:
        groups = db.list_groups()
        matching = [g for g in groups if g["name"].lower() == group.lower()]
        if matching:
            group_id = matching[0]["id"]
        elif not dry_run:
            group_id = db.create_group(group)
            console.print(f"[green]✓[/] Created group '{group}'")

    # Extract URLs from file
    content = file_path.read_text(encoding="utf-8")
    urls = _extract_urls(content, file_path.suffix.lower())

    # Deduplicate by domain
    domains: dict[str, str] = {}  # domain -> first URL that produced it
    for url in urls:
        try:
            parsed = urlparse(url)
            host = parsed.hostname
            if host and host not in domains:
                domains[host] = url
        except ValueError:
            continue

    if not domains:
        console.print("[yellow]No URLs found in file.[/]")
        return

    # Show what we'll import
    table = Table(title=f"{'[DRY RUN] ' if dry_run else ''}Importing {len(domains)} domain rules")
    table.add_column("Domain", style="cyan")
    table.add_column("Source URL", style="dim")
    table.add_column("Browser")
    table.add_column("Profile")

    for domain, source_url in sorted(domains.items()):
        table.add_row(
            f"*.{domain}",
            source_url[:60] + ("…" if len(source_url) > 60 else ""),
            browser_row["name"],
            profile or "-",
        )

    console.print(table)

    if dry_run:
        console.print(f"\n[yellow]Dry run — no rules created.[/] Remove --dry-run to import.")
        return

    created = 0
    skipped = 0
    existing_rules = db.list_rules()
    existing_patterns = {r.pattern.lower() for r in existing_rules}

    for domain in sorted(domains.keys()):
        pattern = f"*.{domain}"
        if pattern.lower() in existing_patterns:
            skipped += 1
            continue
        db.add_rule(
            pattern=pattern,
            pattern_type="domain",
            browser_id=browser_row["id"],
            profile_id=profile_id,
            group_id=group_id,
            incognito=incognito,
        )
        created += 1

    console.print(f"\n[green]✓[/] Created {created} rules, skipped {skipped} duplicates.")


def _extract_urls(content: str, extension: str) -> list[str]:
    """Extract URLs from file content based on format."""
    import re

    if extension in (".yml", ".yaml"):
        # Extract all string values that look like URLs
        url_pattern = re.compile(r"https?://[^\s'\"]+")
        return url_pattern.findall(content)
    elif extension == ".csv":
        urls = []
        for line in content.strip().splitlines()[1:]:  # skip header
            parts = line.split(",")
            if parts:
                candidate = parts[0].strip().strip('"')
                if candidate.startswith("http"):
                    urls.append(candidate)
        return urls
    else:
        # Plain text or unknown — extract anything that looks like a URL
        url_pattern = re.compile(r"https?://[^\s'\"]+")
        return url_pattern.findall(content)


@rule_app.command("remove")
def rule_remove(rule_id: int = typer.Argument(help="Rule ID to remove")):
    """Remove a routing rule."""
    db = _get_db()
    if db.remove_rule(rule_id):
        console.print(f"[green]✓[/] Rule #{rule_id} removed.")
    else:
        console.print(f"[red]Rule #{rule_id} not found.[/]")
        raise typer.Exit(1)


@rule_app.command("reorder")
def rule_reorder(
    rule_id: int = typer.Argument(help="Rule ID to move"),
    position: int = typer.Option(..., "--position", "-p", help="New priority position"),
):
    """Change a rule's priority position."""
    db = _get_db()
    if db.reorder_rule(rule_id, position):
        console.print(f"[green]✓[/] Rule #{rule_id} moved to position {position}.")
    else:
        console.print(f"[red]Rule #{rule_id} not found.[/]")
        raise typer.Exit(1)


# --- Group commands ---


@group_app.command("create")
def group_create(name: str = typer.Argument(help="Group name")):
    """Create a new rule group."""
    db = _get_db()
    try:
        group_id = db.create_group(name)
        console.print(f"[green]✓[/] Group '{name}' created (#{group_id}).")
    except Exception:
        console.print(f"[red]Group '{name}' already exists.[/]")
        raise typer.Exit(1)


@group_app.command("list")
def group_list():
    """List all rule groups."""
    db = _get_db()
    groups = db.list_groups()

    if not groups:
        console.print("No groups defined. Create one with [cyan]bifrost group create <name>[/].")
        return

    table = Table(title="Rule Groups")
    table.add_column("Name", style="cyan")
    table.add_column("Rules", justify="right")

    for g in groups:
        table.add_row(g["name"], str(g["rule_count"]))

    console.print(table)


@app.command("config")
def config_cmd(
    key: str = typer.Argument(help="Config key (e.g., default_action, default_browser, verbose_log)"),
    value: str = typer.Argument(None, help="Value to set (omit to read current value)"),
):
    """Get or set a configuration value."""
    db = _get_db()
    if value is None:
        current = db.get_config(key, "[not set]")
        console.print(f"{key} = {current}")
    else:
        db.set_config(key, value)
        console.print(f"[green]✓[/] {key} = {value}")


if __name__ == "__main__":
    app()
