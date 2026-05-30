import pytest
from unittest.mock import AsyncMock

from burnbox.config import AppConfig
from burnbox.client import BurnBoxClient
from burnbox.models import Session, InboxMessage
from burnbox.providers.registry import select_provider
from burnbox.session import SessionStore


class TestFullFlow:
    @pytest.mark.asyncio
    async def test_register_poll_burn(self, tmp_path):
        provider = AsyncMock()
        provider.name = "testmock"
        provider.is_alive.return_value = True
        provider.register.return_value = Session(
            address="auto@test.com", account_id="acc1",
            token="tok1", provider_name="testmock", created_at=0.0,
        )
        msg = InboxMessage(id="m1", sender="x@y.com", subject="Verify", content="Code: 4455")
        provider.fetch_messages.return_value = [msg]
        provider.delete_account.return_value = True

        store = SessionStore(dir=tmp_path)
        config = AppConfig(copy_address=False)
        client = BurnBoxClient(provider=provider, session_store=store, config=config)

        session = await client.register()
        assert session.address == "auto@test.com"

        loaded = store.load()
        assert loaded is not None
        assert loaded.address == "auto@test.com"

        messages = await client.fetch_new(seen_ids=set())
        assert len(messages) == 1
        assert "4455" in messages[0].content

        result = await client.burn()
        assert result is True
        assert store.load() is None

    @pytest.mark.asyncio
    async def test_register_keep_resume_burn(self, tmp_path):
        provider = AsyncMock()
        provider.name = "testmock"
        provider.is_alive.return_value = True
        provider.register.return_value = Session(
            address="keep@test.com", account_id="acc2",
            token="tok2", provider_name="testmock", created_at=0.0,
        )
        provider.fetch_messages.return_value = []
        provider.delete_account.return_value = True

        store = SessionStore(dir=tmp_path)
        config = AppConfig(copy_address=False)
        client = BurnBoxClient(provider=provider, session_store=store, config=config)

        session = await client.register()
        assert session.address == "keep@test.com"

        assert store.load() is not None

        client2 = BurnBoxClient(provider=provider, session_store=store, config=config)
        resumed = await client2.resume()
        assert resumed.address == "keep@test.com"

        result = await client2.burn()
        assert result is True
        assert store.load() is None


class TestProviderSelection:
    @pytest.mark.asyncio
    async def test_select_alive_provider(self):
        alive = AsyncMock()
        alive.name = "alive"
        alive.is_alive.return_value = True

        dead = AsyncMock()
        dead.name = "dead"
        dead.is_alive.return_value = False

        result = await select_provider([dead, alive])
        assert result.name == "alive"

    @pytest.mark.asyncio
    async def test_preferred_provider(self):
        a = AsyncMock()
        a.name = "a"
        a.is_alive.return_value = True

        b = AsyncMock()
        b.name = "b"
        b.is_alive.return_value = True

        result = await select_provider([a, b], preferred="b")
        assert result.name == "b"


class TestDetectorIntegration:
    def test_code_detection_in_message(self):
        from burnbox.detectors import detect_codes, detect_links

        content = "Your verification code: 8472\nClick https://example.com/verify to confirm"
        codes = detect_codes(content)
        links = detect_links(content)

        assert len(codes) >= 1
        assert any(c.value == "8472" for c in codes)
        assert len(links) == 1
        assert "https://example.com/verify" in links[0]
