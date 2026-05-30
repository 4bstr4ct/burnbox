from __future__ import annotations

from burnbox.exceptions import APIError

_PATH_UNSAFE = frozenset("/\\..")


def safe_path_segment(value: str) -> str:
    if not value:
        raise APIError(400, "Invalid ID: empty")
    for ch in value:
        if ch in _PATH_UNSAFE:
            raise APIError(400, f"Invalid ID: {value!r}")
    return value
