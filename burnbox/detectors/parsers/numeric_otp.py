from __future__ import annotations

import re

from burnbox.detectors.base import CodeMatch, MessageContext
from burnbox.detectors.i18n import CONTEXT_BOOST_WORDS

_GENERIC_OTP = re.compile(r"\b(\d{4,8})\b")
_PROXIMITY = 80

_BOOST_FLAT: list[re.Pattern[str]] = []
for _lang, words in CONTEXT_BOOST_WORDS.items():
    for w in words:
        try:
            _BOOST_FLAT.append(re.compile(w, re.IGNORECASE))
        except re.error:
            continue

_BASE_CONFIDENCE = 0.3
_BOOST_AMOUNT = 0.3
_MAX_CONFIDENCE = 0.8


class NumericOtpParser:
    name: str = "NumericOtpParser"
    priority: int = 20

    def __init__(
        self,
        base_confidence: float = _BASE_CONFIDENCE,
        boost_amount: float = _BOOST_AMOUNT,
        max_confidence: float = _MAX_CONFIDENCE,
    ) -> None:
        self._base = base_confidence
        self._boost = boost_amount
        self._max = max_confidence

    def parse(self, text: str, context: MessageContext) -> list[CodeMatch]:
        matches: list[CodeMatch] = []
        seen_values: set[str] = set()
        lower_text = text.lower()

        for m in _GENERIC_OTP.finditer(text):
            value = m.group(1)
            if value in seen_values:
                continue

            conf = self._base
            window_start = max(0, m.start() - _PROXIMITY)
            window_end = min(len(lower_text), m.end() + _PROXIMITY)
            window = lower_text[window_start:window_end]
            if any(p.search(window) for p in _BOOST_FLAT):
                conf = min(conf + self._boost, self._max)

            ctx_boost = self._context_boost(context)
            if ctx_boost:
                conf = min(conf + ctx_boost, self._max)

            matches.append(CodeMatch(
                value=value,
                start=m.start(1),
                end=m.end(1),
                kind="numeric_otp",
                source_parser=self.name,
                confidence=conf,
            ))
            seen_values.add(value)
        return matches

    def _context_boost(self, context: MessageContext) -> float:
        lower_subject = context.subject.lower()
        if any(p.search(lower_subject) for p in _BOOST_FLAT):
            return self._boost * 0.5
        return 0.0
