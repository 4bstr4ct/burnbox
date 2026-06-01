from __future__ import annotations

import json
import logging
import os
import pathlib
import uuid
from dataclasses import asdict

from burnbox.models import Session

logger = logging.getLogger(__name__)

_DEFAULT_DIR = pathlib.Path.home() / ".config" / "burnbox"
_SESSION_FILE = "session.json"


class SessionStore:
    def __init__(self, store_dir: pathlib.Path | None = None) -> None:
        self._dir = store_dir or _DEFAULT_DIR
        self._file = self._dir / _SESSION_FILE

    def save(self, session: Session) -> None:
        old_mask = os.umask(0o077)
        try:
            self._dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        finally:
            os.umask(old_mask)
        data = asdict(session)
        tmp = self._dir / f"session.{uuid.uuid4().hex}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
        finally:
            os.close(fd)
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
            logger.warning(
                "Session file %s: expected dict, got %s", self._file, type(data).__name__
            )
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
        except FileNotFoundError as exc:
            logger.debug("Session file already absent: %s: %s", self._file, exc)
        except OSError as exc:
            logger.warning("Failed to delete session file %s: %s", self._file, exc)
