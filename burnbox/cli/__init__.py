from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from burnbox import __version__
from burnbox.config import load_config
from burnbox.providers.base import Provider

from burnbox.cli.commands import _run, _run_address, _run_resume

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

app = typer.Typer(
    invoke_without_command=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=False,
)
console = Console()

logger = logging.getLogger(__name__)


def _version_callback(value: bool) -> None:
    if value:
        print(f"burnbox {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    poll: Annotated[
        Optional[float],
        typer.Option("--poll", "-p", help="Polling interval in seconds"),
    ] = None,
    timeout: Annotated[
        Optional[float],
        typer.Option("--timeout", "-t", help="HTTP request timeout"),
    ] = None,
    keep: Annotated[
        bool,
        typer.Option("--keep", "-k", help="Keep account alive after exit"),
    ] = False,
    no_clipboard: Annotated[
        bool,
        typer.Option("--no-clipboard", help="Do not copy to clipboard"),
    ] = False,
    no_notify: Annotated[
        bool,
        typer.Option("--no-notify", help="Disable desktop notifications"),
    ] = False,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="Provider: tempfastmail, mailtm, guerrillamail"),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version", "-v", help="Show version", callback=_version_callback, is_eager=True
        ),
    ] = False,
) -> None:
    """burnbox - Temporary email that burns after reading."""
    if ctx.invoked_subcommand is not None:
        ctx.ensure_object(dict)
        ctx.obj = {
            "poll": poll,
            "timeout": timeout,
            "keep": keep,
            "provider": provider,
            "no_clipboard": no_clipboard,
            "no_notify": no_notify,
        }
        return

    config = load_config()
    if poll is not None:
        if poll < 0.5:
            console.print("[bold red]--poll must be >= 0.5[/bold red]")
            raise typer.Exit(1)
        config = replace(config, poll_interval=poll)
    if timeout is not None:
        if timeout < 1.0:
            console.print("[bold red]--timeout must be >= 1.0[/bold red]")
            raise typer.Exit(1)
        config = replace(config, timeout=timeout)
    if provider is not None:
        config = replace(config, provider_default=provider)
    if no_clipboard:
        config = replace(config, copy_address=False, copy_code=False)
    if no_notify:
        config = replace(config, notifications=False)

    asyncio.run(_run(config, keep))


@app.command()
def address(
    ctx: typer.Context,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="Provider: tempfastmail, mailtm, guerrillamail"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output address as JSON"),
    ] = False,
) -> None:
    """Generate a temp email address and exit."""
    obj = ctx.obj or {}
    config = load_config()

    provider_name = provider or obj.get("provider")
    if provider_name:
        config = replace(config, provider_default=provider_name)
    if obj.get("no_clipboard"):
        config = replace(config, copy_address=False, copy_code=False)
    if obj.get("no_notify"):
        config = replace(config, notifications=False)

    asyncio.run(_run_address(config, json_output=json_output))


@app.command()
def resume(
    ctx: typer.Context,
    keep: Annotated[
        bool,
        typer.Option("--keep", "-k", help="Keep account alive after exit"),
    ] = False,
) -> None:
    """Reconnect to the last saved session."""
    obj = ctx.obj or {}
    config = load_config()
    if obj.get("no_clipboard"):
        config = replace(config, copy_address=False, copy_code=False)
    if obj.get("no_notify"):
        config = replace(config, notifications=False)

    asyncio.run(_run_resume(config, keep))


@app.command()
def providers() -> None:
    """List available email providers and their status."""
    from burnbox.providers.utils import build_registry

    config = load_config()
    registry = build_registry(config.custom_url)

    results = asyncio.run(_check_providers(registry.all()))

    table = Table(title="burnbox providers", border_style="red")
    table.add_column("Provider", style="bold")
    table.add_column("Custom URL", style="cyan")
    table.add_column("Status", style="bold green")

    for p, alive in results:
        status = "[green]alive[/green]" if alive else "[red]down[/red]"
        custom = "yes" if p.supports_custom_url else "no"
        table.add_row(p.name, custom, status)

    console.print(table)


async def _check_providers(
    providers_list: list[Provider],
) -> list[tuple[Provider, bool]]:
    results: list[tuple[Provider, bool]] = []
    for p in providers_list:
        try:
            alive = await p.is_alive()
        except Exception:
            alive = False
        results.append((p, alive))
        try:
            await p.aclose()
        except Exception:
            pass
    return results


if __name__ == "__main__":
    app()
