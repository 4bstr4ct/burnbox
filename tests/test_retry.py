import pytest
from unittest.mock import AsyncMock, MagicMock

from burnbox.exceptions import APIError, AuthExpiredError
from burnbox.retry import RetryConfig, raise_for_status, retry


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 30.0
        assert cfg.detail_max_len == 200

    def test_custom(self):
        cfg = RetryConfig(max_retries=5, base_delay=0.5, max_delay=10.0, detail_max_len=100)
        assert cfg.max_retries == 5
        assert cfg.base_delay == 0.5
        assert cfg.max_delay == 10.0
        assert cfg.detail_max_len == 100


class TestRaiseForStatus:
    def test_success(self):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        raise_for_status(resp)

    def test_401_raises_auth_expired(self):
        resp = MagicMock()
        http_exc = MagicMock()
        http_exc.response.status_code = 401
        http_exc.response.text = "unauthorized"
        resp.raise_for_status.side_effect = __import__("httpx").HTTPStatusError(
            "401",
            request=MagicMock(),
            response=http_exc.response,
        )
        with pytest.raises(AuthExpiredError):
            raise_for_status(resp)

    def test_500_raises_retryable(self):
        from burnbox.retry import _Retryable

        resp = MagicMock()
        http_exc = MagicMock()
        http_exc.response.status_code = 500
        http_exc.response.text = "server error"
        resp.raise_for_status.side_effect = __import__("httpx").HTTPStatusError(
            "500",
            request=MagicMock(),
            response=http_exc.response,
        )
        with pytest.raises(_Retryable):
            raise_for_status(resp)

    def test_404_raises_api_error(self):
        resp = MagicMock()
        http_exc = MagicMock()
        http_exc.response.status_code = 404
        http_exc.response.text = "not found"
        resp.raise_for_status.side_effect = __import__("httpx").HTTPStatusError(
            "404",
            request=MagicMock(),
            response=http_exc.response,
        )
        with pytest.raises(APIError) as exc_info:
            raise_for_status(resp)
        assert exc_info.value.status_code == 404


class TestRetry:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        fn = AsyncMock(return_value="ok")
        result = await retry(fn)
        assert result == "ok"
        fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self):
        import httpx

        fn = AsyncMock(
            side_effect=[
                httpx.ConnectError("conn refused"),
                "ok",
            ]
        )
        result = await retry(fn, cfg=RetryConfig(max_retries=3, base_delay=0.01))
        assert result == "ok"
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        import httpx

        fn = AsyncMock(
            side_effect=[
                httpx.TimeoutException("timed out"),
                "ok",
            ]
        )
        result = await retry(fn, cfg=RetryConfig(max_retries=3, base_delay=0.01))
        assert result == "ok"
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        import httpx

        fn = AsyncMock(side_effect=httpx.ConnectError("conn refused"))
        with pytest.raises(APIError, match="conn refused"):
            await retry(fn, cfg=RetryConfig(max_retries=2, base_delay=0.01))
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_api_error_not_retried(self):
        fn = AsyncMock(side_effect=APIError(400, "bad request"))
        with pytest.raises(APIError, match="bad request"):
            await retry(fn, cfg=RetryConfig(max_retries=3, base_delay=0.01))
        fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_expired_not_retried(self):
        fn = AsyncMock(side_effect=AuthExpiredError("expired"))
        with pytest.raises(AuthExpiredError):
            await retry(fn, cfg=RetryConfig(max_retries=3, base_delay=0.01))
        fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_5xx_then_succeeds(self):
        from burnbox.retry import _Retryable

        fn = AsyncMock(
            side_effect=[
                _Retryable(0.01),
                "ok",
            ]
        )
        result = await retry(fn, cfg=RetryConfig(max_retries=3, base_delay=0.01))
        assert result == "ok"
        assert fn.call_count == 2

    @pytest.mark.asyncio
    async def test_connect_error_on_final_attempt(self):
        import httpx

        fn = AsyncMock(side_effect=httpx.ConnectError("down"))
        with pytest.raises(APIError, match="down"):
            await retry(fn, cfg=RetryConfig(max_retries=1, base_delay=0.01))
