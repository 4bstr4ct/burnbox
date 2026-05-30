from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

from burnbox import __version__
from burnbox.client import BurnBoxClient
from burnbox.config import AppConfig, load_config
from burnbox.detectors import copy_to_clipboard, detect_codes, detect_links, extract_best_code, MessageContext
from burnbox.exceptions import AuthExpiredError, BurnBoxError, SessionError
from burnbox.models import InboxMessage
from burnbox.notifications import send_notification
from burnbox.providers.base import Provider
from burnbox.providers.registry import ProviderRegistry, select_provider
from burnbox.providers.utils import build_registry
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

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_ERRORS = 5


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

    escaped = msg.content.replace("[", "\\[")
    content_parts: list[Text] = [Text(escaped)]
    codes = detect_codes(msg.content, MessageContext(sender=msg.sender, subject=msg.subject))
    links = detect_links(msg.content)

    if codes and config.copy_code:
        best = extract_best_code(codes)
        if best:
            copy_to_clipboard(best)
            content_parts.append(Text.from_markup(f"\n  [dim]Copied code: {best}[/dim]"))
            if config.notifications:
                send_notification("burnbox", f"Code: {best}")

    if codes:
        code_str = ", ".join(c.value for c in codes)
        content_parts.append(Text.from_markup(f"\n  [bold green]Codes: {code_str}[/bold green]"))
    if links:
        content_parts.append(Text.from_markup(f"\n  [bold blue]Links: {len(links)} found[/bold blue]"))

    combined = Text()
    for part in content_parts:
        combined.append(part)

    panel = Panel(
        combined,
        title=header,
        border_style="red",
        padding=(1, 2),
    )
    console.print(panel)


def _build_registry(config: AppConfig) -> ProviderRegistry:
    return build_registry(config.custom_url)


async def _select_provider(config: AppConfig) -> tuple[Provider, list[Provider]]:
    registry = _build_registry(config)
    all_providers = registry.all()
    provider = await select_provider(all_providers, preferred=config.provider_default)
    if not provider:
        raise BurnBoxError("No available providers. Check your network.")
    unused = [p for p in all_providers if p is not provider]
    return provider, unused


def _get_provider_by_name(config: AppConfig, name: str) -> tuple[Provider | None, list[Provider]]:
    registry = _build_registry(config)
    provider = registry.get(name)
    unused = [p for p in registry.all() if p is not provider] if provider else registry.all()
    return provider, unused


async def _close_unused(unused: list[Provider]) -> None:
    for p in unused:
        try:
            await p.aclose()
        except Exception:
            pass


async def _poll_loop(client: BurnBoxClient, config: AppConfig) -> None:
    seen_ids: set[str] = set()
    consecutive_errors = 0

    with Status("burnbox: waiting for drops...", console=console, spinner="dots") as status:
        while True:
            try:
                new_mails = await client.fetch_new(seen_ids)
                consecutive_errors = 0
                if new_mails:
                    status.stop()
                    for mail in new_mails:
                        _render_message(mail, config)
                        seen_ids.add(mail.id)
                    status.update(f"burnbox: waiting for drops... [dim]({len(seen_ids)} seen)[/dim]")
                    status.start()
                else:
                    status.update(f"burnbox: waiting for drops... [dim]({len(seen_ids)} seen)[/dim]")
            except AuthExpiredError:
                raise
            except BurnBoxError as exc:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    raise BurnBoxError(
                        f"Too many consecutive errors ({consecutive_errors}). Last: {exc}"
                    ) from exc
                console.print(f"[red]Error: {exc}[/red]")
            except KeyboardInterrupt:
                return
            except Exception as exc:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    raise BurnBoxError(
                        f"Too many consecutive errors ({consecutive_errors}). Last: {exc}"
                    ) from exc
                logger.warning("Unexpected error in poll loop: %s", exc)

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
        typer.Option("--provider", help="Provider to use: mailtm, mailgw, dropmail, guerrillamail"),
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
        config = replace(config, poll_interval=poll)
    if timeout is not None:
        config = replace(config, timeout=timeout)
    if provider is not None:
        config = replace(config, provider_default=provider)

    asyncio.run(_run(config, keep))


async def _run(config: AppConfig, keep: bool) -> None:
    provider, unused = await _select_provider(config)
    store = SessionStore()
    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    console.print(Panel(
        "Temp email that burns after reading",
        title="[bold red]burnbox[/bold red]",
        border_style="red",
        padding=(0, 2),
    ))
    try:
        session = await client.register()
        console.print()
        console.print(f"  [bold]Provider:[/bold] {provider.name}")
        console.print(f"  [bold]Address:[/bold]  [green]{session.address}[/green]")
        if config.copy_address:
            copy_to_clipboard(session.address)
            console.print("[dim]  Address copied to clipboard[/dim]")
        console.print()
        console.print("[dim]  Ctrl+C to exit and burn · --keep to preserve · burnbox resume[/dim]\n")
        await _poll_loop(client, config)
    except KeyboardInterrupt:
        pass
    except BurnBoxError as exc:
        console.print(f"[bold red]Critical failure: {exc}[/bold red]")
    finally:
        if not keep and client.session:
            try:
                if await client.burn():
                    console.print("[dim]Burned.[/dim]")
                else:
                    console.print("[bold red]Failed to burn account.[/bold red]")
            except Exception:
                console.print("[bold red]Failed to burn account.[/bold red]")
        elif keep and client.session:
            console.print("[dim]Kept alive. Resume with: [bold]burnbox resume[/bold][/dim]")
        await _close_unused(unused)
        await provider.aclose()


@app.command()
def address(
    ctx: typer.Context,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="Provider to use: mailtm, mailgw, dropmail, guerrillamail"),
    ] = None,
) -> None:
    """Generate a temp email address and exit."""
    obj = ctx.obj or {}
    config = load_config()

    provider_name = provider or obj.get("provider")
    if provider_name:
        config = replace(config, provider_default=provider_name)

    asyncio.run(_run_address(config))


async def _run_address(config: AppConfig) -> None:
    provider, unused = await _select_provider(config)
    store = SessionStore()
    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    try:
        session = await client.register()
        console.print(f"[green]{session.address}[/green]")
        if config.copy_address:
            copy_to_clipboard(session.address)
            console.print("[dim]Address copied to clipboard.[/dim]")
    except KeyboardInterrupt:
        pass
    finally:
        if client.session:
            try:
                await client.burn()
            except Exception:
                pass
        store.delete()
        await _close_unused(unused)
        await provider.aclose()


@app.command()
def resume(
    ctx: typer.Context,
    keep: Annotated[
        bool,
        typer.Option("--keep", "-k", help="Keep account alive after exit"),
    ] = False,
) -> None:
    """Reconnect to the last saved session."""
    config = load_config()

    asyncio.run(_run_resume(config, keep))


async def _run_resume(config: AppConfig, keep: bool) -> None:
    store = SessionStore()
    saved = store.load()
    if not saved:
        console.print("[bold red]No saved session found. Run 'burnbox' first.[/bold red]")
        return

    provider, unused = _get_provider_by_name(config, saved.provider_name)
    if not provider:
        console.print(f"[bold red]Unknown provider '{saved.provider_name}' in saved session.[/bold red]")
        store.delete()
        await _close_unused(unused)
        return

    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    try:
        session = await client.resume()
        console.print(f"  [bold]Provider:[/bold] {provider.name}")
        console.print(f"  [bold]Address:[/bold]  [green]{session.address}[/green]")
        console.print()
        console.print("[dim]  Ctrl+C to exit and burn · --keep to preserve[/dim]\n")
        await _poll_loop(client, config)
    except KeyboardInterrupt:
        pass
    except SessionError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
    except BurnBoxError as exc:
        console.print(f"[bold red]Critical failure: {exc}[/bold red]")
    finally:
        if not keep and client.session:
            try:
                if await client.burn():
                    console.print("[dim]Burned.[/dim]")
                else:
                    console.print("[bold red]Failed to burn account.[/bold red]")
            except Exception:
                console.print("[bold red]Failed to burn account.[/bold red]")
        elif keep and client.session:
            console.print("[dim]Kept alive. Resume with: [bold]burnbox resume[/bold][/dim]")
        await _close_unused(unused)
        await provider.aclose()


if __name__ == "__main__":
    app()
