from __future__ import annotations

import json
import logging
import os
import pathlib
import stat
import uuid
from dataclasses import asdict

from burnbox.models import Session

logger = logging.getLogger(__name__)

_DEFAULT_DIR = pathlib.Path.home() / ".config" / "burnbox"
_SESSION_FILE = "session.json"


class SessionStore:
    def __init__(self, dir: pathlib.Path | None = None) -> None:
        self._dir = dir or _DEFAULT_DIR
        self._file = self._dir / _SESSION_FILE

    def save(self, session: Session) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self._dir, stat.S_IRWXU)
        data = asdict(session)
        tmp = self._dir / f"session.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, self._file)
        logger.info("Session saved to %s", self._file)

    def load(self) -> Session | None:
        try:
            raw = self._file.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            logger.warning("Cannot read session file %s: %s", self._file, exc)
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Corrupt session file %s: %s", self._file, exc)
            return None

        if not isinstance(data, dict):
            logger.warning("Session file %s: expected dict, got %s", self._file, type(data).__name__)
            return None

        required = ("address", "token", "provider_name", "account_id")
        if not all(k in data for k in required):
            logger.warning("Session file %s: missing required keys", self._file)
            return None

        if not data["address"] or not isinstance(data["address"], str):
            logger.warning("Session file %s: invalid address", self._file)
            return None

        try:
            return Session(
                address=data["address"],
                account_id=data["account_id"],
                token=data["token"],
                provider_name=data["provider_name"],
                created_at=float(data.get("created_at", 0.0)),
            )
        except (TypeError, ValueError) as exc:
            logger.warning("Session file %s: invalid field types: %s", self._file, exc)
            return None

    def delete(self) -> None:
        try:
            self._file.unlink()
            logger.info("Session file deleted: %s", self._file)
        except OSError:
            pass
