import logging
import time

import httpx

from burnbox.config import Config
from burnbox.exceptions import APIError, AuthExpiredError

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(
        self,
        config: Config | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config or Config()
        self._client = client or httpx.Client(timeout=self._config.request_timeout)
        self._token: str | None = None

    @property
    def token(self) -> str | None:
        return self._token

    @token.setter
    def token(self, value: str | None) -> None:
        self._token = value

    def request(
        self,
        method: str,
        endpoint: str,
        body: dict | None = None,
        auth: bool = True,
    ) -> dict:
        url = f"{self._config.base_url}{endpoint}"
        headers: dict[str, str] = {}
        if auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        for attempt in range(1, self._config.retry_max_attempts + 1):
            try:
                response = self._client.request(
                    method, url, json=body, headers=headers
                )
                if response.status_code == 401 and auth:
                    raise AuthExpiredError("Authentication token expired")
                if response.status_code == 204:
                    return {}
                response.raise_for_status()
                return response.json()
            except AuthExpiredError:
                raise
            except httpx.HTTPStatusError as exc:
                raise APIError(
                    status_code=exc.response.status_code,
                    detail=exc.response.text,
                ) from exc
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt < self._config.retry_max_attempts:
                    delay = min(
                        self._config.retry_base_delay * (2 ** (attempt - 1)),
                        self._config.retry_max_delay,
                    )
                    logger.warning(
                        "Request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt,
                        self._config.retry_max_attempts,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                else:
                    raise APIError(status_code=0, detail=str(exc)) from exc

    def close(self) -> None:
        self._client.close()
