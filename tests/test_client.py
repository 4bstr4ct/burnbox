import pytest

from burnbox.client import BurnBoxClient
from burnbox.config import AppConfig
from burnbox.exceptions import AuthExpiredError, SessionError
from burnbox.models import Session, InboxMessage
from burnbox.session import SessionStore


@pytest.fixture
def mock_session_store(tmp_path):
    return SessionStore(store_dir=tmp_path)


class TestBurnBoxClient:
    @pytest.mark.asyncio
    async def test_register(self, mock_provider, mock_session_store):
        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(),
        )
        session = await client.register()
        assert session.address == "test@example.com"
        mock_provider.register.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_saves_session(self, mock_provider, mock_session_store):
        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(copy_address=False),
        )
        await client.register()
        loaded = mock_session_store.load()
        assert loaded is not None
        assert loaded.address == "test@example.com"

    @pytest.mark.asyncio
    async def test_fetch_new(self, mock_provider, mock_session_store):
        msg = InboxMessage(id="1", sender="a@b.c", subject="Hi", content="Code: 1234")
        mock_provider.fetch_messages.return_value = [msg]
        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(),
        )
        await client.register()
        new = await client.fetch_new(seen_ids=set())
        assert len(new) == 1

    @pytest.mark.asyncio
    async def test_burn(self, mock_provider, mock_session_store):
        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(),
        )
        await client.register()
        result = await client.burn()
        assert result is True
        assert mock_session_store.load() is None

    @pytest.mark.asyncio
    async def test_burn_without_session(self, mock_provider, mock_session_store):
        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(),
        )
        result = await client.burn()
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_with_valid_token(self, mock_provider, mock_session_store):
        session = Session(
            address="test@example.com", account_id="1",
            token="tok", provider_name="mailtm", created_at=0.0,
        )
        mock_session_store.save(session)
        mock_provider.fetch_messages.return_value = []

        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(),
        )
        result = await client.resume()
        assert result.address == "test@example.com"

    @pytest.mark.asyncio
    async def test_resume_no_session(self, mock_provider, mock_session_store):
        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(),
        )
        with pytest.raises(SessionError, match="No saved session"):
            await client.resume()

    @pytest.mark.asyncio
    async def test_resume_expired_session(self, mock_provider, mock_session_store):
        session = Session(
            address="test@example.com", account_id="1",
            token="tok", provider_name="mailtm", created_at=0.0,
        )
        mock_session_store.save(session)
        mock_provider.fetch_messages.side_effect = AuthExpiredError("Session expired")

        client = BurnBoxClient(
            provider=mock_provider,
            session_store=mock_session_store,
            config=AppConfig(),
        )
        with pytest.raises(SessionError, match="Session expired"):
            await client.resume()
        assert mock_session_store.load() is None
