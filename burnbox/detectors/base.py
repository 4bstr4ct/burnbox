from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CodeMatch:
    value: str
    start: int
    end: int
    kind: str
    source_parser: str
    confidence: float


@dataclass(frozen=True)
class MessageContext:
    sender: str = ""
    subject: str = ""


@runtime_checkable
class CodeParser(Protocol):
    name: str
    priority: int

    def parse(self, text: str, context: MessageContext) -> list[CodeMatch]: ...
