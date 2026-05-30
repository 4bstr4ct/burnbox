from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

_CLIPBOARD_TIMEOUT = 5
_CLEAR_AFTER_SECONDS = 30.0

_ongoing_clear_tasks: list[asyncio.Task[Any]] = []


def _is_wayland() -> bool:
    import os
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _clear_clipboard() -> bool:
    try:
        return copy_to_clipboard("")
    except Exception:
        return False


async def copy_to_clipboard_auto_clear(text: str, clear_after: float = _CLEAR_AFTER_SECONDS) -> bool:
    if not copy_to_clipboard(text):
        return False

    async def _clear_later() -> None:
        await asyncio.sleep(clear_after)
        _clear_clipboard()
        logger.debug("Clipboard auto-cleared after %.0fs", clear_after)

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_clear_later())
        _ongoing_clear_tasks.append(task)
        task.add_done_callback(lambda t: _ongoing_clear_tasks.remove(t) if t in _ongoing_clear_tasks else None)
    except RuntimeError:
        pass
    return True


def copy_to_clipboard(text: str) -> bool:
    if _is_wayland():
        try:
            subprocess.run(
                ["wl-copy"],
                check=True,
                timeout=_CLIPBOARD_TIMEOUT,
                input=text.encode(),
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    if _is_macos():
        try:
            subprocess.run(
                ["pbcopy"],
                check=True,
                timeout=_CLIPBOARD_TIMEOUT,
                input=text.encode(),
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    if _is_windows():
        try:
            subprocess.run(
                ["clip.exe"],
                check=True,
                timeout=_CLIPBOARD_TIMEOUT,
                input=text.encode(),
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    for cmd, args in [
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("xsel", ["xsel", "--clipboard", "--input"]),
    ]:
        try:
            subprocess.run(args, input=text.encode(), check=True, timeout=_CLIPBOARD_TIMEOUT)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    logger.warning("Could not copy to clipboard")
    return False
