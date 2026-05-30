from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

_NOTIFY_TIMEOUT = 5


def _is_linux() -> bool:
    return platform.system() == "Linux"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _notify_linux(title: str, body: str) -> bool:
    try:
        subprocess.run(
            ["notify-send", "--expire-time=5000", title, body],
            check=True,
            timeout=_NOTIFY_TIMEOUT,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _notify_macos(title: str, body: str) -> bool:
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    escaped_body = body.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{escaped_body}" with title "{escaped_title}"'
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            timeout=_NOTIFY_TIMEOUT,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def send_notification(title: str, body: str) -> bool:
    if _is_linux():
        return _notify_linux(title, body)
    if _is_macos():
        return _notify_macos(title, body)
    logger.debug("Notifications not supported on %s", platform.system())
    return False
