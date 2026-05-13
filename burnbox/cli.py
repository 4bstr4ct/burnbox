# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
#     "html2text",
#     "rich",
#     "typer",
# ]
# ///

import logging
import time
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

from burnbox import AuthExpiredError, BurnBoxClient, BurnBoxError, Config

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)

__version__ = "1.0.0"

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


def _render_mail(mail) -> None:
    header = Text()
    header.append("From: ", style="bold cyan")
    header.append(mail.sender)
    header.append("    ")
    header.append("Subject: ", style="bold yellow")
    header.append(mail.subject)

    panel = Panel(
        Text(mail.content),
        title=header,
        border_style="red",
        padding=(1, 2),
    )
    console.print(panel)


def _poll_loop(client: BurnBoxClient, config: Config) -> None:
    seen_ids: set[str] = set()

    with Status(
        "burnbox: waiting for drops...",
        console=console,
        spinner="dots",
    ) as status:
        while True:
            try:
                new_mails = client.fetch_new_messages(seen_ids)
                if new_mails:
                    status.stop()
                    for mail in new_mails:
                        _render_mail(mail)
                        seen_ids.add(mail.id)
                    status.update(
                        "burnbox: waiting for drops... "
                        f"[dim]({len(seen_ids)} seen)[/dim]"
                    )
                    status.start()
                else:
                    status.update(
                        "burnbox: waiting for drops... "
                        f"[dim]({len(seen_ids)} seen)[/dim]"
                    )
            except AuthExpiredError:
                console.print(
                    "[bold red]Token expired. Use [bold]burnbox resume[/bold] to reconnect.[/bold red]"
                )
                break
            except BurnBoxError as exc:
                console.print(f"[red]Error: {exc}[/red]")

            time.sleep(config.polling_interval)


def _burn_or_keep(client: BurnBoxClient, keep: bool) -> None:
    if not keep:
        if client.burn():
            console.print("[dim]Burned.[/dim]")
        else:
            console.print("[bold red]Failed to burn account.[/bold red]")
    else:
        console.print(f"[dim]Kept alive. Resume with: [bold]burnbox resume[/bold][/dim]")


@app.callback()
def main(
    ctx: typer.Context,
    poll: Annotated[
        float,
        typer.Option("--poll", "-p", help="Polling interval in seconds"),
    ] = 5.0,
    timeout: Annotated[
        float,
        typer.Option("--timeout", "-t", help="HTTP request timeout in seconds"),
    ] = 10.0,
    keep: Annotated[
        bool,
        typer.Option("--keep", "-k", help="Keep account alive after exit (don't burn)"),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    """burnbox - Temporary email that burns after reading."""
    if ctx.invoked_subcommand is not None:
        ctx.ensure_object(dict)
        ctx.obj["poll"] = poll
        ctx.obj["timeout"] = timeout
        ctx.obj["keep"] = keep
        return

    console.print(Panel.fit("[bold red]burnbox[/bold red] - Temp Email CLI", style="red"))
    config = Config(polling_interval=poll, request_timeout=timeout)

    with BurnBoxClient(config) as client:
        try:
            email = client.register()
            console.print()
            console.print(f"  [bold]Address:[/bold]  [green]{email}[/green]")
            console.print(f"  [bold]Password:[/bold] [dim]{client.password}[/dim]")
            console.print("[dim]  Listening for drops... (Ctrl+C to exit)[/dim]\n")
            _poll_loop(client, config)
        except KeyboardInterrupt:
            pass
        except BurnBoxError as exc:
            console.print(f"[bold red]Critical failure: {exc}[/bold red]")
            return

        _burn_or_keep(client, keep)


@app.command()
def login(
    ctx: typer.Context,
    address: Annotated[
        str,
        typer.Argument(help="Email address"),
    ],
    password: Annotated[
        str,
        typer.Argument(help="Account password"),
    ],
) -> None:
    """Connect to an existing account."""
    console.print(Panel.fit("[bold red]burnbox[/bold red] - Temp Email CLI", style="red"))

    obj = ctx.obj or {}
    config = Config(
        polling_interval=obj.get("poll", 5.0),
        request_timeout=obj.get("timeout", 10.0),
    )
    keep = obj.get("keep", False)

    with BurnBoxClient(config) as client:
        try:
            client.login(address, password)
            console.print()
            console.print(f"  [bold]Address:[/bold]  [green]{address}[/green]")
            console.print("[dim]  Listening for drops... (Ctrl+C to exit)[/dim]\n")
            _poll_loop(client, config)
        except KeyboardInterrupt:
            pass
        except BurnBoxError as exc:
            console.print(f"[bold red]Critical failure: {exc}[/bold red]")
            return

        _burn_or_keep(client, keep)


@app.command()
def resume(
    ctx: typer.Context,
) -> None:
    """Reconnect to the last saved session."""
    console.print(Panel.fit("[bold red]burnbox[/bold red] - Temp Email CLI", style="red"))

    obj = ctx.obj or {}
    config = Config(
        polling_interval=obj.get("poll", 5.0),
        request_timeout=obj.get("timeout", 10.0),
    )
    keep = obj.get("keep", False)

    with BurnBoxClient(config) as client:
        try:
            address = client.resume()
            console.print()
            console.print(f"  [bold]Address:[/bold]  [green]{address}[/green]")
            console.print("[dim]  Listening for drops... (Ctrl+C to exit)[/dim]\n")
            _poll_loop(client, config)
        except KeyboardInterrupt:
            pass
        except BurnBoxError as exc:
            console.print(f"[bold red]Critical failure: {exc}[/bold red]")
            return

        _burn_or_keep(client, keep)


if __name__ == "__main__":
    app()
