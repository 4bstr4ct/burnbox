import logging
import secrets
import string

from burnbox.api import APIClient
from burnbox.exceptions import NoDomainsError, TokenError
from burnbox.schemas import extract_members

logger = logging.getLogger(__name__)


def _generate_secure_str(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


_SPECIAL = "!@#$%&*"
_PASSWORD_LEN = 16
_MIN_PASSWORD_LEN = 8


def _generate_password(length: int = _PASSWORD_LEN) -> str:
    if length < _MIN_PASSWORD_LEN:
        raise ValueError(f"Password length must be >= {_MIN_PASSWORD_LEN}, got {length}")
    while True:
        chars = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice(_SPECIAL),
        ]
        pool = string.ascii_letters + string.digits + _SPECIAL
        chars += [secrets.choice(pool) for _ in range(length - len(chars))]
        secrets.SystemRandom().shuffle(chars)
        password = "".join(chars)
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in _SPECIAL for c in password)
        ):
            return password


class AccountService:
    def __init__(self, api: APIClient) -> None:
        self._api = api
        self.address: str | None = None
        self._password: str | None = None
        self.account_id: str | None = None

    def register(self) -> tuple[str, str, str]:
        logger.info("Fetching available domains...")
        domains_data = self._api.request("GET", "/domains", auth=False)
        members = extract_members(domains_data)
        if not members:
            raise NoDomainsError("No domains available")

        domain = members[0]["domain"]
        self.address = f"{_generate_secure_str()}@{domain}"
        self._password = _generate_password()

        logger.info("Registering account: %s", self.address)
        account_data = self._api.request(
            "POST",
            "/accounts",
            body={"address": self.address, "password": self._password},
            auth=False,
        )

        self.account_id = account_data.get("id")

        logger.info("Requesting authorization token...")
        token_data = self._api.request(
            "POST",
            "/token",
            body={"address": self.address, "password": self._password},
            auth=False,
        )

        token = token_data.get("token")
        if not token:
            raise TokenError("Failed to retrieve authentication token")

        self._api.token = token
        logger.info("Token acquired successfully")
        return self.address, self._password, self.account_id

    def login(self, address: str, password: str) -> tuple[str, str]:
        self.address = address
        self._password = password
        token_data = self._api.request(
            "POST",
            "/token",
            body={"address": address, "password": password},
            auth=False,
        )
        token = token_data.get("token")
        if not token:
            raise TokenError("Failed to retrieve authentication token")
        self._api.token = token

        me = self._api.request("GET", "/me")
        self.account_id = me.get("id")
        return address, self.account_id

    def delete(self) -> None:
        if not self.account_id:
            return
        self._api.request("DELETE", f"/accounts/{self.account_id}")
        logger.info("Account %s burned", self.address)
