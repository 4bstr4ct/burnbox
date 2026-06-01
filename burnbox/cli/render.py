from __future__ import annotations

import html as _html

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from burnbox.config import AppConfig
from burnbox.detectors import detect_codes, detect_links, extract_best_code, MessageContext
from burnbox.models import InboxMessage
from burnbox.notifications import send_notification

console = Console()
_MAX_DISPLAY_CODES = 5


def _render_message(msg: InboxMessage, config: AppConfig) -> str | None:
    header = Text()
    header.append("From: ", style="bold cyan")
    header.append(msg.sender)
    header.append("    ")
    header.append("Subject: ", style="bold yellow")
    header.append(msg.subject)

    msg_panel = Panel(
        Text(_html.unescape(msg.content)),
        title=header,
        border_style="red",
        padding=(1, 2),
    )
    console.print(msg_panel)

    codes = detect_codes(msg.content, MessageContext(sender=msg.sender, subject=msg.subject))
    links = detect_links(msg.content)
    best: str | None = None

    otp_codes = [c for c in codes if c.kind != "reset_link"]
    reset_links = [c for c in codes if c.kind == "reset_link"]

    if otp_codes and config.copy_code:
        best = extract_best_code(codes)
        if best:
            if config.notifications:
                send_notification("burnbox", "Verification code received")

    if otp_codes or reset_links:
        detected_parts: list[Text] = []
        if otp_codes:
            top = sorted(otp_codes, key=lambda c: c.confidence, reverse=True)[:_MAX_DISPLAY_CODES]
            code_values = ", ".join(c.value for c in top)
            code_line = f"Code: {code_values}"
            if best and config.copy_code:
                code_line += " (copied, clears in 30s)"
            detected_parts.append(Text.from_markup(f"[bold green]{code_line}[/bold green]"))
            if len(otp_codes) > _MAX_DISPLAY_CODES:
                detected_parts.append(Text.from_markup(f"[dim]  +{len(otp_codes) - _MAX_DISPLAY_CODES} more[/dim]"))
        if reset_links:
            n_links = len(reset_links)
            link_word = "link" if n_links == 1 else "links"
            detected_parts.append(Text.from_markup(f"[bold blue]Link: {n_links} verification {link_word}[/bold blue]"))
        elif links:
            detected_parts.append(Text.from_markup(f"[bold blue]Link: {len(links)} found[/bold blue]"))

        combined = Text()
        for i, part in enumerate(detected_parts):
            if i > 0:
                combined.append("\n")
            combined.append(part)

        detected_panel = Panel(
            combined,
            title="[bold]Detected[/bold]",
            border_style="green",
            padding=(0, 1),
        )
        console.print(detected_panel)

    return best
