from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CodeMatch:
    value: str
    start: int
    end: int
    kind: str  # "otp" (generic) or "labeled" (preceded by keyword)


_LABELED_PATTERNS = [
    re.compile(
        r"(?:code|код|pin|otp|код подтверждения)[:\s]*(\d{4,8})", re.IGNORECASE
    ),
]
_GENERIC_OTP = re.compile(r"\b(\d{4,8})\b")
_LINK_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def detect_codes(text: str) -> list[CodeMatch]:
    matches: list[CodeMatch] = []
    seen_values: set[str] = set()

    # Labeled patterns first (higher confidence)
    for pattern in _LABELED_PATTERNS:
        for m in pattern.finditer(text):
            if m.group(1) not in seen_values:
                matches.append(CodeMatch(
                    value=m.group(1), start=m.start(1), end=m.end(1), kind="labeled"
                ))
                seen_values.add(m.group(1))

    # Generic OTP pattern (skip values already found by labeled)
    for m in _GENERIC_OTP.finditer(text):
        if m.group(1) not in seen_values:
            matches.append(CodeMatch(
                value=m.group(1), start=m.start(), end=m.end(), kind="otp"
            ))
            seen_values.add(m.group(1))

    return matches


def detect_links(text: str) -> list[str]:
    return _LINK_PATTERN.findall(text)


def extract_best_code(codes: list[CodeMatch]) -> str | None:
    """Auto-copy to clipboard if exactly one code found, else return None."""
    if len(codes) == 1:
        copy_to_clipboard(codes[0].value)
        return codes[0].value
    return None


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    # Fallback: try xclip/xsel
    for cmd, args in [
        ("xclip", ["xclip", "-selection", "clipboard"]),
        ("xsel", ["xsel", "--clipboard", "--input"]),
    ]:
        try:
            subprocess.run(args, input=text.encode(), check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    logger.warning("Could not copy to clipboard")
    return False
