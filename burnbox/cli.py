from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

from burnbox import __version__
from burnbox.client import BurnBoxClient
from burnbox.config import AppConfig, load_config
from burnbox.detectors import detect_codes, detect_links, extract_best_code
from burnbox.exceptions import BurnBoxError, SessionError
from burnbox.models import InboxMessage, Session
from burnbox.providers.base import Provider
from burnbox.providers.mailtm import MailTmProvider
from burnbox.providers.mailgw import MailGwProvider
from burnbox.providers.onesecmail import OneSecMailProvider
from burnbox.providers.registry import ProviderRegistry, select_provider
from burnbox.session import SessionStore

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


def _version_callback(value: bool) -> None:
    if value:
        print(f"burnbox {__version__}")
        raise typer.Exit()


def _render_message(msg: InboxMessage, config: AppConfig) -> None:
    header = Text()
    header.append("From: ", style="bold cyan")
    header.append(msg.sender)
    header.append("    ")
    header.append("Subject: ", style="bold yellow")
    header.append(msg.subject)

    content = msg.content
    codes = detect_codes(content)
    links = detect_links(content)

    if codes and config.copy_code:
        best = extract_best_code(codes)
        if best:
            content += f"\n  [dim]Copied code: {best}[/dim]"

    if codes:
        code_str = ", ".join(c.value for c in codes)
        content += f"\n  [bold green]Codes: {code_str}[/bold green]"
    if links:
        content += f"\n  [bold blue]Links: {len(links)} found[/bold blue]"

    panel = Panel(
        Text(content),
        title=header,
        border_style="red",
        padding=(1, 2),
    )
    console.print(panel)


def _build_registry(config: AppConfig) -> ProviderRegistry:
    registry = ProviderRegistry()
    if config.custom_url:
        registry.register(MailTmProvider(base_url=config.custom_url))
    else:
        registry.register(MailTmProvider())
    registry.register(MailGwProvider())
    registry.register(OneSecMailProvider())
    registry.discover_plugins()
    return registry


async def _select_provider(config: AppConfig) -> Provider:
    registry = _build_registry(config)
    provider = await select_provider(registry.all(), preferred=config.provider_default)
    if not provider:
        raise BurnBoxError("No available providers. Check your network.")
    return provider


def _get_provider_by_name(config: AppConfig, name: str) -> Provider | None:
    """Get a provider by name from registry without health check."""
    registry = _build_registry(config)
    return registry.get(name)


async def _poll_loop(client: BurnBoxClient, config: AppConfig) -> None:
    seen_ids: set[str] = set()

    with Status("burnbox: waiting for drops...", console=console, spinner="dots") as status:
        while True:
            try:
                new_mails = await client.fetch_new(seen_ids)
                if new_mails:
                    status.stop()
                    for mail in new_mails:
                        _render_message(mail, config)
                        seen_ids.add(mail.id)
                    status.update(f"burnbox: waiting for drops... [dim]({len(seen_ids)} seen)[/dim]")
                    status.start()
                else:
                    status.update(f"burnbox: waiting for drops... [dim]({len(seen_ids)} seen)[/dim]")
            except BurnBoxError as exc:
                console.print(f"[red]Error: {exc}[/red]")

            await asyncio.sleep(config.poll_interval)


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
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="Provider name (mailtm, mailgw, 1secmail)"),
    ] = None,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version", callback=_version_callback, is_eager=True),
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
        }
        return

    config = load_config()
    if poll is not None:
        config = AppConfig(
            provider_default=config.provider_default,
            custom_url=config.custom_url,
            poll_interval=poll,
            timeout=config.timeout,
            copy_address=config.copy_address,
            copy_code=config.copy_code,
        )
    if timeout is not None:
        config = AppConfig(
            provider_default=config.provider_default,
            custom_url=config.custom_url,
            poll_interval=config.poll_interval,
            timeout=timeout,
            copy_address=config.copy_address,
            copy_code=config.copy_code,
        )
    if provider is not None:
        config = AppConfig(
            provider_default=provider,
            custom_url=config.custom_url,
            poll_interval=config.poll_interval,
            timeout=config.timeout,
            copy_address=config.copy_address,
            copy_code=config.copy_code,
        )

    asyncio.run(_run(config, keep))


async def _run(config: AppConfig, keep: bool) -> None:
    provider = await _select_provider(config)
    store = SessionStore()
    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    console.print(Panel.fit("[bold red]burnbox[/bold red] - Temp Email CLI", style="red"))
    try:
        session = await client.register()
        console.print()
        console.print(f"  [bold]Address:[/bold]  [green]{session.address}[/green]")
        if config.copy_address:
            console.print("[dim]  Address copied to clipboard[/dim]")
        console.print("[dim]  Listening for drops... (Ctrl+C to exit)[/dim]\n")
        await _poll_loop(client, config)
    except KeyboardInterrupt:
        pass
    except BurnBoxError as exc:
        console.print(f"[bold red]Critical failure: {exc}[/bold red]")
        return

    if not keep:
        if await client.burn():
            console.print("[dim]Burned.[/dim]")
        else:
            console.print("[bold red]Failed to burn account.[/bold red]")
    else:
        console.print("[dim]Kept alive. Resume with: [bold]burnbox resume[/bold][/dim]")


@app.command()
def address(
    ctx: typer.Context,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="Provider name"),
    ] = None,
) -> None:
    """Generate a temp email address and exit."""
    obj = ctx.obj or {}
    config = load_config()

    provider_name = provider or obj.get("provider")
    if provider_name:
        config = AppConfig(
            provider_default=provider_name,
            custom_url=config.custom_url,
            poll_interval=config.poll_interval,
            timeout=config.timeout,
            copy_address=config.copy_address,
            copy_code=config.copy_code,
        )

    asyncio.run(_run_address(config))


async def _run_address(config: AppConfig) -> None:
    provider = await _select_provider(config)
    store = SessionStore()
    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    session = await client.register()
    console.print(f"[green]{session.address}[/green]")
    if config.copy_address:
        console.print("[dim]Address copied to clipboard.[/dim]")


@app.command()
def resume(
    ctx: typer.Context,
) -> None:
    """Reconnect to the last saved session."""
    obj = ctx.obj or {}
    keep = obj.get("keep", False)
    config = load_config()

    asyncio.run(_run_resume(config, keep))


async def _run_resume(config: AppConfig, keep: bool) -> None:
    store = SessionStore()
    saved = store.load()
    if not saved:
        console.print("[bold red]No saved session found. Run 'burnbox' first.[/bold red]")
        return

    # Use the provider that created the session, not a random alive one
    provider = _get_provider_by_name(config, saved.provider_name)
    if not provider:
        console.print(f"[bold red]Unknown provider '{saved.provider_name}' in saved session.[/bold red]")
        store.delete()
        return

    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    try:
        session = await client.resume()
        console.print(f"  [bold]Address:[/bold]  [green]{session.address}[/green]")
        console.print("[dim]  Listening for drops... (Ctrl+C to exit)[/dim]\n")
        await _poll_loop(client, config)
    except KeyboardInterrupt:
        pass
    except SessionError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        return
    except BurnBoxError as exc:
        console.print(f"[bold red]Critical failure: {exc}[/bold red]")
        return

    if not keep:
        if await client.burn():
            console.print("[dim]Burned.[/dim]")
    else:
        console.print("[dim]Kept alive. Resume with: [bold]burnbox resume[/bold][/dim]")


if __name__ == "__main__":
    app()
