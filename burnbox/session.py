from __future__ import annotations

import json
import logging
import os
import pathlib
import stat

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
        data = session.to_dict()
        self._file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(self._file, stat.S_IRUSR | stat.S_IWUSR)
        logger.info("Session saved to %s", self._file)

    def load(self) -> Session | None:
        if not self._file.exists():
            return None
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            if "address" in data and "token" in data:
                return Session(
                    address=data["address"],
                    account_id=data.get("account_id", ""),
                    token=data["token"],
                    provider_name=data.get("provider_name", "mailtm"),
                    created_at=data.get("created_at", 0.0),
                )
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def delete(self) -> None:
        try:
            self._file.unlink()
            logger.info("Session file deleted: %s", self._file)
        except OSError:
            pass
