import time

import httpx
import pytest

from burnbox.api import APIClient
from burnbox.config import Config
from burnbox.exceptions import APIError, AuthExpiredError


def _make_response(status_code: int, json_data: dict | None = None, text: str = "") -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "https://api.mail.tm/test"),
    )


class TestAPIRequest:
    def test_request_200_returns_json(self):
        resp = _make_response(200, {"key": "value"})
        mock_client = httpx.Client()
        mock_client.request = lambda method, url, **kw: resp

        api = APIClient(client=mock_client)
        result = api.request("GET", "/test")
        assert result == {"key": "value"}
        api.close()

    def test_request_204_returns_empty_dict(self):
        resp = _make_response(204)
        mock_client = httpx.Client()
        mock_client.request = lambda method, url, **kw: resp

        api = APIClient(client=mock_client)
        result = api.request("DELETE", "/test")
        assert result == {}
        api.close()

    def test_request_401_with_auth_raises_auth_expired(self):
        resp = _make_response(401)
        mock_client = httpx.Client()
        mock_client.request = lambda method, url, **kw: resp

        api = APIClient(client=mock_client)
        with pytest.raises(AuthExpiredError):
            api.request("GET", "/test", auth=True)
        api.close()

    def test_request_401_without_auth_raises_api_error(self):
        resp = _make_response(401, text="unauthorized")
        resp.read = lambda: None

        mock_client = httpx.Client()
        mock_client.request = lambda method, url, **kw: _raise_status(resp, 401)

        api = APIClient(client=mock_client)
        with pytest.raises(APIError) as exc_info:
            api.request("GET", "/test", auth=False)
        assert exc_info.value.status_code == 401
        api.close()

    def test_request_4xx_raises_api_error(self):
        resp = _make_response(429, text="rate limited")
        resp.read = lambda: None

        mock_client = httpx.Client()
        mock_client.request = lambda method, url, **kw: _raise_status(resp, 429)

        api = APIClient(client=mock_client)
        with pytest.raises(APIError) as exc_info:
            api.request("GET", "/test")
        assert exc_info.value.status_code == 429
        api.close()

    def test_request_sends_bearer_token_when_auth_and_token_set(self):
        captured_headers = {}

        def capture_request(method, url, json=None, headers=None):
            captured_headers.update(headers or {})
            return _make_response(200, {"ok": True})

        mock_client = httpx.Client()
        mock_client.request = capture_request

        api = APIClient(client=mock_client)
        api.token = "my-jwt"
        api.request("GET", "/test", auth=True)
        assert captured_headers["Authorization"] == "Bearer my-jwt"
        api.close()

    def test_request_no_auth_header_when_auth_false(self):
        captured_headers = {}

        def capture_request(method, url, json=None, headers=None):
            captured_headers.update(headers or {})
            return _make_response(200, {"ok": True})

        mock_client = httpx.Client()
        mock_client.request = capture_request

        api = APIClient(client=mock_client)
        api.token = "my-jwt"
        api.request("GET", "/test", auth=False)
        assert "Authorization" not in captured_headers
        api.close()

    def test_request_no_auth_header_when_no_token(self):
        captured_headers = {}

        def capture_request(method, url, json=None, headers=None):
            captured_headers.update(headers or {})
            return _make_response(200, {"ok": True})

        mock_client = httpx.Client()
        mock_client.request = capture_request

        api = APIClient(client=mock_client)
        api.request("GET", "/test", auth=True)
        assert "Authorization" not in captured_headers
        api.close()

    def test_request_retries_on_connect_error(self, monkeypatch):
        call_count = 0

        def flaky_request(method, url, **kw):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("connection failed")
            return _make_response(200, {"ok": True})

        monkeypatch.setattr(time, "sleep", lambda _: None)

        mock_client = httpx.Client()
        mock_client.request = flaky_request

        api = APIClient(client=mock_client)
        result = api.request("GET", "/test")
        assert result == {"ok": True}
        assert call_count == 3
        api.close()

    def test_request_retries_on_timeout(self, monkeypatch):
        call_count = 0

        def flaky_request(method, url, **kw):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("timeout")
            return _make_response(200, {"ok": True})

        monkeypatch.setattr(time, "sleep", lambda _: None)

        mock_client = httpx.Client()
        mock_client.request = flaky_request

        api = APIClient(client=mock_client)
        result = api.request("GET", "/test")
        assert result == {"ok": True}
        api.close()

    def test_request_exhausted_retries_raises_api_error(self, monkeypatch):
        monkeypatch.setattr(time, "sleep", lambda _: None)

        mock_client = httpx.Client()
        mock_client.request = lambda method, url, **kw: (_ for _ in ()).throw(
            httpx.ConnectError("connection failed")
        )

        api = APIClient(client=mock_client)
        with pytest.raises(APIError) as exc_info:
            api.request("GET", "/test")
        assert exc_info.value.status_code == 0
        api.close()

    def test_request_sends_body(self):
        captured = {}

        def capture_request(method, url, json=None, headers=None):
            captured["method"] = method
            captured["json"] = json
            return _make_response(200, {"ok": True})

        mock_client = httpx.Client()
        mock_client.request = capture_request

        api = APIClient(client=mock_client)
        api.request("POST", "/test", body={"key": "val"})
        assert captured["method"] == "POST"
        assert captured["json"] == {"key": "val"}
        api.close()

    def test_close_calls_client_close(self):
        closed = [False]

        class FakeClient:
            def close(self):
                closed[0] = True
            def request(self, *a, **kw):
                return _make_response(200, {})

        api = APIClient(client=FakeClient())
        api.close()
        assert closed[0]


def _raise_status(resp: httpx.Response, status_code: int):
    resp._status_code = status_code

    def raise_it():
        raise httpx.HTTPStatusError(
            message="error",
            request=httpx.Request("GET", "https://api.mail.tm/test"),
            response=resp,
        )

    raise_it()
