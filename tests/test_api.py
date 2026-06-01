import pytest
from unittest.mock import AsyncMock

from burnbox.api import BurnBox, Message
from burnbox.config import AppConfig
from burnbox.detectors.engine import ParserEngine
from burnbox.models import InboxMessage, Session


@pytest.fixture
def mock_session_store(tmp_path):
    from burnbox.session import SessionStore

    return SessionStore(store_dir=tmp_path)


class TestMessage:
    def test_properties(self):
        engine = ParserEngine()
        inner = InboxMessage(id="1", sender="a@b.c", subject="Verify", content="code: 1234")
        msg = Message(inner, engine)
        assert msg.id == "1"
        assert msg.sender == "a@b.c"
        assert msg.subject == "Verify"
        assert msg.content == "code: 1234"

    def test_codes(self):
        engine = ParserEngine()
        inner = InboxMessage(id="1", sender="a@b.c", subject="Verify", content="code: 1234")
        msg = Message(inner, engine)
        assert len(msg.codes) >= 1
        assert any(c.value == "1234" for c in msg.codes)

    def test_best_code(self):
        engine = ParserEngine()
        inner = InboxMessage(id="1", sender="a@b.c", subject="Verify", content="code: 1234")
        msg = Message(inner, engine)
        assert msg.best_code == "1234"

    def test_best_code_none(self):
        engine = ParserEngine()
        inner = InboxMessage(id="1", sender="a@b.c", subject="Hi", content="no codes here")
        msg = Message(inner, engine)
        assert msg.best_code is None

    def test_links(self):
        engine = ParserEngine()
        inner = InboxMessage(
            id="1", sender="a@b.c", subject="Hi", content="Click https://example.com"
        )
        msg = Message(inner, engine)
        assert len(msg.links) == 1

    def test_codes_cached(self):
        engine = ParserEngine()
        inner = InboxMessage(id="1", sender="a@b.c", subject="Verify", content="code: 1234")
        msg = Message(inner, engine)
        first = msg.codes
        second = msg.codes
        assert first is second


class TestBurnBox:
    @pytest.mark.asyncio
    async def test_address(self, mock_provider, mock_session_store):
        client = AsyncMock()
        client.session = Session(
            address="test@example.com",
            account_id="1",
            token="tok",
            provider_name="mailtm",
            created_at=0.0,
        )
        client.fetch_new = AsyncMock(return_value=[])
        client.burn = AsyncMock(return_value=True)
        box = BurnBox(provider=mock_provider, client=client, config=AppConfig())
        assert box.address == "test@example.com"

    @pytest.mark.asyncio
    async def test_fetch_new(self, mock_provider, mock_session_store):
        client = AsyncMock()
        client.session = Session(
            address="test@example.com",
            account_id="1",
            token="tok",
            provider_name="mailtm",
            created_at=0.0,
        )
        msg = InboxMessage(id="1", sender="a@b.c", subject="Hi", content="code: 9999")
        client.fetch_new = AsyncMock(return_value=[msg])
        client.burn = AsyncMock(return_value=True)
        box = BurnBox(provider=mock_provider, client=client, config=AppConfig())
        messages = await box.fetch_new()
        assert len(messages) == 1
        assert messages[0].best_code == "9999"

    @pytest.mark.asyncio
    async def test_context_manager_burns(self, mock_provider):
        client = AsyncMock()
        client.session = Session(
            address="test@example.com",
            account_id="1",
            token="tok",
            provider_name="mailtm",
            created_at=0.0,
        )
        client.burn = AsyncMock(return_value=True)
        box = BurnBox(provider=mock_provider, client=client, config=AppConfig())
        async with box:
            pass
        client.burn.assert_called_once()
        mock_provider.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_message_timeout(self, mock_provider):
        client = AsyncMock()
        client.session = Session(
            address="test@example.com",
            account_id="1",
            token="tok",
            provider_name="mailtm",
            created_at=0.0,
        )
        client.fetch_new = AsyncMock(return_value=[])
        client.burn = AsyncMock(return_value=True)
        box = BurnBox(provider=mock_provider, client=client, config=AppConfig(poll_interval=0.01))
        result = await box.wait_for_message(timeout=0.05)
        assert result is None
