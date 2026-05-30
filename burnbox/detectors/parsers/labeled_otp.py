from __future__ import annotations

import re

from burnbox.detectors.base import CodeMatch, MessageContext
from burnbox.detectors.i18n import OTP_LABELS


def _build_patterns() -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for _lang, labels in OTP_LABELS.items():
        for label in labels:
            try:
                patterns.append(
                    re.compile(
                        rf"(?:{label})[:\s]*(\d{{4,8}})",
                        re.IGNORECASE,
                    )
                )
            except re.error:
                continue
    return patterns


_COMPILED = _build_patterns()


class LabeledOtpParser:
    name: str = "LabeledOtpParser"
    priority: int = 10

    def __init__(self, confidence: float = 0.9) -> None:
        self._confidence = confidence

    def parse(self, text: str, context: MessageContext) -> list[CodeMatch]:
        matches: list[CodeMatch] = []
        seen_values: set[str] = set()
        for pattern in _COMPILED:
            for m in pattern.finditer(text):
                value = m.group(1)
                if value not in seen_values:
                    matches.append(CodeMatch(
                        value=value,
                        start=m.start(1),
                        end=m.end(1),
                        kind="labeled_otp",
                        source_parser=self.name,
                        confidence=self._confidence,
                    ))
                    seen_values.add(value)
        return matches
