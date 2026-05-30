from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

_CLIPBOARD_TIMEOUT = 5


def _is_wayland() -> bool:
    import os
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _is_windows() -> bool:
    return platform.system() == "Windows"


def copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

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
