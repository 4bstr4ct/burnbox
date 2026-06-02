from __future__ import annotations

import json
import logging

from rich.console import Console
from rich.panel import Panel

from burnbox.client import BurnBoxClient
from burnbox.config import AppConfig
from burnbox.exceptions import BurnBoxError, SessionError
from burnbox.providers.utils import close_unused, select_provider, get_provider_by_name
from burnbox.session import SessionStore

from burnbox.cli.poll import _poll_loop

console = Console()
logger = logging.getLogger(__name__)


async def _run(config: AppConfig, keep: bool) -> None:
    from burnbox.detectors import async_copy_to_clipboard

    provider, unused = await select_provider(config)
    store = SessionStore()
    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    console.print(
        Panel(
            "Temp email that burns after reading",
            title="[bold red]burnbox[/bold red]",
            border_style="red",
            padding=(0, 2),
        )
    )
    try:
        session = await client.register()
        console.print()
        console.print(f"  [bold]Provider:[/bold] {provider.name}")
        console.print(f"  [bold]Address:[/bold]  [green]{session.address}[/green]")
        if config.copy_address:
            await async_copy_to_clipboard(session.address)
            console.print("[dim]  Address copied to clipboard[/dim]")
        console.print()
        console.print(
            "[dim]  Ctrl+C to exit and burn · --keep to preserve · burnbox resume[/dim]\n"
        )
        await _poll_loop(client, config)
    except KeyboardInterrupt:
        console.print("[dim]Interrupted.[/dim]")
    except BurnBoxError as exc:
        console.print(f"[bold red]Critical failure: {exc}[/bold red]")
    finally:
        if not keep and client.session:
            try:
                if await client.burn():
                    console.print("[dim]Burned.[/dim]")
                else:
                    console.print("[bold red]Failed to burn account.[/bold red]")
            except (OSError, BurnBoxError) as exc:
                logger.warning("Failed to burn account: %s", exc)
                console.print("[bold red]Failed to burn account.[/bold red]")
        elif keep and client.session:
            console.print("[dim]Kept alive. Resume with: [bold]burnbox resume[/bold][/dim]")
        await close_unused(unused)
        await provider.aclose()


async def _run_address(config: AppConfig, json_output: bool = False) -> None:
    from burnbox.detectors import async_copy_to_clipboard

    provider, unused = await select_provider(config)
    store = SessionStore()
    client = BurnBoxClient(provider=provider, session_store=store, config=config)

    try:
        session = await client.register()
        if json_output:
            print(json.dumps({"address": session.address, "provider": provider.name}))
        else:
            console.print(f"[green]{session.address}[/green]")
            if config.copy_address:
                await async_copy_to_clipboard(session.address)
                console.print("[dim]Address copied to clipboard.[/dim]")
    except KeyboardInterrupt:
        if not json_output:
            console.print("[dim]Interrupted.[/dim]")
    finally:
        if client.session:
            try:
                await client.burn()
            except OSError as exc:
                logger.warning("Failed to burn account on interrupt: %s", exc)
        store.delete()
        await close_unused(unused)
        await provider.aclose()


async def _run_resume(config: AppConfig, keep: bool) -> None:
    store = SessionStore()
    saved = store.load()
    if not saved:
        console.print("[bold red]No saved session found. Run 'burnbox' first.[/bold red]")
        return

    provider, unused = get_provider_by_name(config, saved.provider_name)
    if not provider:
        console.print(
            f"[bold red]Unknown provider '{saved.provider_name}' in saved session.[/bold red]"
        )
        store.delete()
        await close_unused(unused)
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
        console.print("[dim]Interrupted.[/dim]")
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
            except (OSError, BurnBoxError) as exc:
                logger.warning("Failed to burn account: %s", exc)
                console.print("[bold red]Failed to burn account.[/bold red]")
        elif keep and client.session:
            console.print("[dim]Kept alive. Resume with: [bold]burnbox resume[/bold][/dim]")
        await close_unused(unused)
        await provider.aclose()
