import json
import logging
import os
import pathlib
import stat
from typing import Any

from burnbox.account import AccountService
from burnbox.api import APIClient
from burnbox.config import Config
from burnbox.exceptions import BurnBoxError
from burnbox.messages import MessageService
from burnbox.models import InboxMessage

logger = logging.getLogger(__name__)

SESSION_DIR = pathlib.Path.home() / ".config" / "burnbox"
SESSION_FILE = SESSION_DIR / "session.json"


def _save_session(address: str, password: str, account_id: str | None) -> None:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(SESSION_DIR, stat.S_IRWXU)
    data: dict[str, Any] = {"address": address, "password": password}
    if account_id:
        data["account_id"] = account_id
    SESSION_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(SESSION_FILE, stat.S_IRUSR | stat.S_IWUSR)
    logger.info("Session saved to %s", SESSION_FILE)


def _delete_session() -> None:
    try:
        SESSION_FILE.unlink()
        logger.info("Session file deleted: %s", SESSION_FILE)
    except OSError:
        pass


def _load_session() -> dict[str, str] | None:
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        if "address" in data and "password" in data:
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


class BurnBoxClient:
    def __init__(
        self,
        config: Config | None = None,
        api: APIClient | None = None,
    ) -> None:
        self._config = config or Config()
        self._api = api or APIClient(config=self._config)
        self._account = AccountService(self._api)
        self._messages = MessageService(self._api)
        self.address: str | None = None
        self.password: str | None = None
        self.account_id: str | None = None

    def register(self) -> str:
        address, password, account_id = self._account.register()
        self.address = address
        self.password = password
        self.account_id = account_id
        _save_session(address, password, account_id)
        return address

    def login(self, address: str, password: str) -> str:
        self.address, self.account_id = self._account.login(address, password)
        self.password = password
        _save_session(address, password, self.account_id)
        return self.address

    def resume(self) -> str:
        session = _load_session()
        if not session:
            raise BurnBoxError("No saved session found. Run 'burnbox' first.")
        address = session["address"]
        password = session["password"]
        account_id = session.get("account_id")
        self.address, self.account_id = self._account.login(address, password)
        self.password = password
        self.account_id = account_id
        self._account.account_id = account_id
        _save_session(address, password, account_id)
        return self.address

    def burn(self) -> bool:
        if not self._account.account_id:
            logger.warning("No account_id — cannot burn")
            return False
        try:
            self._account.delete()
        except BurnBoxError:
            logger.warning("Failed to burn account %s", self.address)
            return False
        _delete_session()
        return True

    def fetch_new_messages(self, seen_ids: set[str]) -> list[InboxMessage]:
        return self._messages.fetch_new(seen_ids)

    def close(self) -> None:
        self._api.close()

    def __enter__(self) -> "BurnBoxClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
