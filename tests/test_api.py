import httpx
import pytest

from burnbox.api import APIClient
from burnbox.config import Config
from burnbox.exceptions import APIError, AuthExpiredError, BurnBoxError


def test_api_client_default_config():
    api = APIClient()
    assert api.token is None


def test_api_client_custom_config():
    config = Config(base_url="https://example.com", request_timeout=5.0)
    api = APIClient(config=config)
    assert api._config.base_url == "https://example.com"
    api.close()


def test_api_client_inject_httpx_client():
    client = httpx.Client()
    api = APIClient(client=client)
    assert api._client is client
    api.close()


def test_api_token_property():
    api = APIClient()
    api.token = "test-token"
    assert api.token == "test-token"
    api.close()


def test_api_error_status_code():
    err = APIError(status_code=429, detail="rate limited")
    assert err.status_code == 429
    assert "429" in str(err)


def test_auth_expired_error_is_burnbox_error():
    assert issubclass(AuthExpiredError, BurnBoxError)


def test_config_frozen():
    config = Config()
    with pytest.raises(AttributeError):
        config.base_url = "changed"
