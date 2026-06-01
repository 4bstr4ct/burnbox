from __future__ import annotations

import html as _html

from burnbox.detectors.base import CodeMatch, MessageContext
from burnbox.detectors.clipboard import (
    async_copy_to_clipboard,
    copy_to_clipboard,
    copy_to_clipboard_auto_clear,
)
from burnbox.detectors.engine import ParserEngine

_engine = ParserEngine()


def _clean_text(text: str) -> str:
    return _html.unescape(text)


def detect_codes(text: str, context: MessageContext | None = None) -> list[CodeMatch]:
    return _engine.parse(_clean_text(text), context)


def detect_links(text: str) -> list[str]:
    return ParserEngine.detect_links(_clean_text(text))


def extract_best_code(codes: list[CodeMatch]) -> str | None:
    best = _engine.best_code(codes)
    return best.value if best else None


__all__ = [
    "CodeMatch",
    "MessageContext",
    "ParserEngine",
    "async_copy_to_clipboard",
    "copy_to_clipboard",
    "copy_to_clipboard_auto_clear",
    "detect_codes",
    "detect_links",
    "extract_best_code",
]
