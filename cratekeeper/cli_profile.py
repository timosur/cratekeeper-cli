"""CLI subcommands for profile management."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def register(app: typer.Typer) -> None:
    """Create and attach the profile sub-app to *app*."""

    profile_app = typer.Typer(help="Inspect and manage configuration profiles")
    app.add_typer(profile_app, name="profile")

    @profile_app.command("list")
    def profile_list() -> None:
        """List defined profiles and mark the active one."""
        from cratekeeper.config import active_profile_name, load_settings

        settings = load_settings()
        if settings is None:
            console.print("No config file found — using the implicit [green]commercial[/green] profile.")
            console.print("Run [bold]crate profile init[/bold] to create a config with multiple profiles.")
            return

        active = active_profile_name(settings)
        table = Table(title="Profiles")
        table.add_column("", style="green")
        table.add_column("Name", style="cyan")
        table.add_column("Buckets", justify="right")
        table.add_column("DJ software")
        table.add_column("Tag format")
        for name, prof in settings.profiles.items():
            marker = "*" if name == active else ""
            table.add_row(marker, name, str(len(prof.buckets)), prof.dj_software, prof.tag_format)
        console.print(table)

    @profile_app.command("show")
    def profile_show(
        name: str = typer.Argument(None, help="Profile name (default: active profile)"),
    ) -> None:
        """Print the fully resolved settings for a profile."""
        from cratekeeper.config import ConfigError, resolve_profile

        try:
            prof = resolve_profile(name)
        except ConfigError as exc:
            console.print(f"[red]Config error:[/red] {exc}")
            raise typer.Exit(1)

        info = prof.describe()
        table = Table(title=f"Profile: {info['name']}")
        table.add_column("Setting", style="cyan")
        table.add_column("Value")
        table.add_row("Buckets", ", ".join(info["buckets"]))
        table.add_row("Fallback", info["fallback"])
        table.add_row("DJ software", info["dj_software"])
        table.add_row("Tag format", info["tag_format"])
        table.add_row("Library target", info["library_target"])
        table.add_row("Data dir", info["data_dir"])
        table.add_row("Required fields", ", ".join(info["required_fields"]))
        sort = info["sort"]
        table.add_row("Sort", "none" if sort is None else f"{', '.join(sort['keys'])} ({sort['direction']})")
        console.print(table)

    @profile_app.command("use")
    def profile_use(
        name: str = typer.Argument(help="Profile name to activate"),
    ) -> None:
        """Set the active profile in the config file."""
        from cratekeeper.config import ConfigError, set_active_profile

        try:
            path = set_active_profile(name)
        except ConfigError as exc:
            console.print(f"[red]Config error:[/red] {exc}")
            raise typer.Exit(1)
        console.print(f"[green]Active profile set to '{name}'[/green] in {path}")

    @profile_app.command("init")
    def profile_init() -> None:
        """Scaffold a config file with commercial + electronic example profiles."""
        from cratekeeper.config import ConfigError, _legacy_data_dir, write_default_config

        try:
            path = write_default_config()
        except ConfigError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Created config at {path}[/green]")
        console.print(
            "[yellow]Note:[/yellow] existing plans in "
            f"[dim]{_legacy_data_dir()}[/dim] are not auto-migrated. "
            "Move them into a profile's data_dir or re-import."
        )
