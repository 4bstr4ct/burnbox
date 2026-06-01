from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from burnbox.detectors.base import CodeMatch, LINK_PATTERN, MessageContext
from burnbox.detectors.i18n import URL_CODE_PARAMS

_CODE_VALUE_RE = re.compile(r"^[A-Za-z0-9\-_.+/=]{3,64}$")
_NUMERIC_VALUE_RE = re.compile(r"^\d{4,8}$")


class UrlCodeParser:
    name: str = "UrlCodeParser"
    priority: int = 5

    def __init__(self, confidence: float = 0.85) -> None:
        self._confidence = confidence

    def parse(self, text: str, context: MessageContext) -> list[CodeMatch]:
        matches: list[CodeMatch] = []
        seen_values: set[str] = set()

        for m in LINK_PATTERN.finditer(text):
            url_str = m.group(0)
            try:
                parsed = urlparse(url_str)
            except Exception:
                continue

            params = parse_qs(parsed.query)
            for param_name in URL_CODE_PARAMS:
                values = params.get(param_name, [])
                for val in values:
                    if not (_CODE_VALUE_RE.match(val) or _NUMERIC_VALUE_RE.match(val)):
                        continue
                    if val not in seen_values:
                        conf = self._confidence
                        if _NUMERIC_VALUE_RE.match(val):
                            conf = min(conf + 0.05, 1.0)
                        matches.append(
                            CodeMatch(
                                value=val,
                                start=m.start(),
                                end=m.end(),
                                kind="url_code",
                                source_parser=self.name,
                                confidence=conf,
                            )
                        )
                        seen_values.add(val)
        return matches
