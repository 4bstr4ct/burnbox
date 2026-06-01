from __future__ import annotations

import asyncio
import logging

from rich.console import Console
from rich.status import Status

from burnbox.client import BurnBoxClient
from burnbox.config import AppConfig
from burnbox.exceptions import AuthExpiredError, BurnBoxError
from burnbox.cli.render import _render_message

console = Console()
logger = logging.getLogger(__name__)
_MAX_CONSECUTIVE_ERRORS = 5


async def _poll_loop(client: BurnBoxClient, config: AppConfig) -> None:
    seen_ids: set[str] = set()
    consecutive_errors = 0

    with Status("burnbox: waiting for drops...", console=console, spinner="dots") as status:
        while True:
            try:
                new_mails = await client.fetch_new(seen_ids)
            except AuthExpiredError:
                raise
            except BurnBoxError as exc:
                consecutive_errors += 1
                if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    raise BurnBoxError(
                        f"Too many consecutive errors ({consecutive_errors}). Last: {exc}"
                    ) from exc
                console.print(f"[red]Error: {exc}[/red]")
                await asyncio.sleep(config.poll_interval)
                continue
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
                continue

            consecutive_errors = 0
            if not new_mails:
                status.update(f"burnbox: waiting for drops... [dim]({len(seen_ids)} seen)[/dim]")
                await asyncio.sleep(config.poll_interval)
                continue

            status.stop()
            last_code: str | None = None
            for mail in new_mails:
                code = _render_message(mail, config)
                if code:
                    last_code = code
                seen_ids.add(mail.id)
            if last_code:
                from burnbox.detectors import (
                    async_copy_to_clipboard,
                    copy_to_clipboard_auto_clear,
                )

                await async_copy_to_clipboard(last_code)
                await copy_to_clipboard_auto_clear(last_code)
            status.update(f"burnbox: waiting for drops... [dim]({len(seen_ids)} seen)[/dim]")
            status.start()

            await asyncio.sleep(config.poll_interval)
