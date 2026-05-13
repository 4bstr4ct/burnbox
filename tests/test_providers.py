import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from burnbox.providers.base import Provider, ProviderSession
from burnbox.providers.mailtm import MailTmProvider
from burnbox.exceptions import NoDomainsError, TokenError


@pytest.fixture
def mock_async_client():
    client = AsyncMock()
    return client


class TestProviderSession:
    def test_session_fields(self):
        s = ProviderSession(
            address="test@example.com",
            account_id="abc123",
            token="tok456",
            provider_name="mailtm",
            created_at=1000.0,
        )
        assert s.address == "test@example.com"
        assert s.account_id == "abc123"
        assert s.token == "tok456"
        assert s.provider_name == "mailtm"
        assert s.password is None

    def test_session_frozen(self):
        s = ProviderSession(
            address="a@b.c", account_id="1", token="t",
            provider_name="mailtm", created_at=0.0,
        )
        with pytest.raises(AttributeError):
            s.address = "new"


class TestMailTmProvider:
    def test_name(self):
        p = MailTmProvider()
        assert p.name == "mailtm"

    def test_supports_custom_url(self):
        p = MailTmProvider()
        assert p.supports_custom_url is True

    @pytest.mark.asyncio
    async def test_is_alive_success(self, mock_async_client):
        mock_async_client.get.return_value = MagicMock(status_code=200)
        p = MailTmProvider(client=mock_async_client)
        assert await p.is_alive() is True

    @pytest.mark.asyncio
    async def test_is_alive_failure(self, mock_async_client):
        mock_async_client.get.side_effect = Exception("connection error")
        p = MailTmProvider(client=mock_async_client)
        assert await p.is_alive() is False

    @pytest.mark.asyncio
    async def test_register(self, mock_async_client):
        domains_resp = MagicMock()
        domains_resp.json.return_value = {"hydra:member": [{"domain": "example.com"}]}
        domains_resp.raise_for_status = MagicMock()

        account_resp = MagicMock()
        account_resp.json.return_value = {"id": "acc123", "address": "test@example.com"}
        account_resp.raise_for_status = MagicMock()

        token_resp = MagicMock()
        token_resp.json.return_value = {"token": "tok456"}
        token_resp.raise_for_status = MagicMock()

        mock_async_client.request = AsyncMock(
            side_effect=[domains_resp, account_resp, token_resp]
        )
        p = MailTmProvider(client=mock_async_client)
        session = await p.register()
        assert isinstance(session, ProviderSession)
        assert session.address.endswith("@example.com")
        assert session.account_id == "acc123"
        assert session.token == "tok456"
        assert session.provider_name == "mailtm"

    @pytest.mark.asyncio
    async def test_register_no_domains(self, mock_async_client):
        domains_resp = MagicMock()
        domains_resp.json.return_value = {"hydra:member": []}
        domains_resp.raise_for_status = MagicMock()
        mock_async_client.request = AsyncMock(return_value=domains_resp)
        p = MailTmProvider(client=mock_async_client)
        with pytest.raises(NoDomainsError):
            await p.register()

    @pytest.mark.asyncio
    async def test_delete_account(self, mock_async_client):
        delete_resp = MagicMock()
        delete_resp.status_code = 204
        mock_async_client.request = AsyncMock(return_value=delete_resp)
        p = MailTmProvider(client=mock_async_client)
        result = await p.delete_account("acc123")
        assert result is True

    @pytest.mark.asyncio
    async def test_fetch_messages(self, mock_async_client):
        list_resp = MagicMock()
        list_resp.json.return_value = {
            "hydra:member": [
                {"id": "msg1", "from": {"address": "sender@test.com"}, "subject": "Hi"}
            ]
        }
        list_resp.raise_for_status = MagicMock()

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "id": "msg1",
            "from": {"address": "sender@test.com"},
            "subject": "Hi",
            "html": "<p>Your code is 1234</p>",
            "text": None,
        }
        detail_resp.raise_for_status = MagicMock()

        mock_async_client.request = AsyncMock(side_effect=[list_resp, detail_resp])
        p = MailTmProvider(client=mock_async_client)
        p._token = "tok456"
        messages = await p.fetch_messages(seen_ids=set())
        assert len(messages) == 1
        assert messages[0].sender == "sender@test.com"
        assert "1234" in messages[0].content

    @pytest.mark.asyncio
    async def test_fetch_messages_filters_seen(self, mock_async_client):
        list_resp = MagicMock()
        list_resp.json.return_value = {
            "hydra:member": [
                {"id": "msg1", "from": {"address": "a@b.c"}, "subject": "Old"},
                {"id": "msg2", "from": {"address": "c@d.c"}, "subject": "New"},
            ]
        }
        list_resp.raise_for_status = MagicMock()

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "id": "msg2", "from": {"address": "c@d.c"},
            "subject": "New", "html": None, "text": "New message",
        }
        detail_resp.raise_for_status = MagicMock()

        mock_async_client.request = AsyncMock(side_effect=[list_resp, detail_resp])
        p = MailTmProvider(client=mock_async_client)
        p._token = "tok456"
        messages = await p.fetch_messages(seen_ids={"msg1"})
        assert len(messages) == 1
        assert messages[0].id == "msg2"

    @pytest.mark.asyncio
    async def test_login(self, mock_async_client):
        token_resp = MagicMock()
        token_resp.json.return_value = {"token": "logtok"}
        token_resp.raise_for_status = MagicMock()

        me_resp = MagicMock()
        me_resp.json.return_value = {"id": "me123"}
        me_resp.raise_for_status = MagicMock()

        mock_async_client.request = AsyncMock(side_effect=[token_resp, me_resp])
        p = MailTmProvider(client=mock_async_client)
        session = await p.login("user@example.com", "pass123")
        assert session.address == "user@example.com"
        assert session.account_id == "me123"
        assert session.token == "logtok"

    @pytest.mark.asyncio
    async def test_login_token_error(self, mock_async_client):
        token_resp = MagicMock()
        token_resp.json.return_value = {}
        token_resp.raise_for_status = MagicMock()
        mock_async_client.request = AsyncMock(return_value=token_resp)
        p = MailTmProvider(client=mock_async_client)
        with pytest.raises(TokenError):
            await p.login("user@example.com", "pass123")

    @pytest.mark.asyncio
    async def test_delete_account_failure(self, mock_async_client):
        mock_async_client.request = AsyncMock(side_effect=Exception("network error"))
        p = MailTmProvider(client=mock_async_client)
        result = await p.delete_account("acc123")
        assert result is False

    def test_provider_protocol_compliance(self):
        p = MailTmProvider()
        assert isinstance(p, Provider)

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_async_client):
        mock_async_client.aclose = AsyncMock()
        p = MailTmProvider(client=mock_async_client)
        async with p:
            pass
        mock_async_client.aclose.assert_called_once()


from burnbox.providers.mailgw import MailGwProvider
from burnbox.providers.onesecmail import OneSecMailProvider


class TestMailGwProvider:
    def test_name(self):
        p = MailGwProvider()
        assert p.name == "mailgw"

    def test_supports_custom_url(self):
        p = MailGwProvider()
        assert p.supports_custom_url is True

    def test_default_url(self):
        p = MailGwProvider()
        assert p._base_url == "https://api.mail.gw"

    @pytest.mark.asyncio
    async def test_is_alive_success(self, mock_async_client):
        mock_async_client.get.return_value = MagicMock(status_code=200)
        p = MailGwProvider(client=mock_async_client)
        assert await p.is_alive() is True


class TestOneSecMailProvider:
    def test_name(self):
        p = OneSecMailProvider()
        assert p.name == "1secmail"

    def test_supports_custom_url(self):
        p = OneSecMailProvider()
        assert p.supports_custom_url is False

    @pytest.mark.asyncio
    async def test_is_alive(self, mock_async_client):
        mock_async_client.get.return_value = MagicMock(status_code=200)
        p = OneSecMailProvider(client=mock_async_client)
        assert await p.is_alive() is True

    @pytest.mark.asyncio
    async def test_register(self, mock_async_client):
        gen_resp = MagicMock()
        gen_resp.json.return_value = ["1secmail.com", "1secmail.org"]
        gen_resp.raise_for_status = MagicMock()
        mock_async_client.get = AsyncMock(return_value=gen_resp)
        p = OneSecMailProvider(client=mock_async_client)
        session = await p.register()
        assert session.address.endswith("@1secmail.com") or session.address.endswith("@1secmail.org")
        assert session.provider_name == "1secmail"
        assert session.token == ""

    @pytest.mark.asyncio
    async def test_delete_always_true(self, mock_async_client):
        p = OneSecMailProvider(client=mock_async_client)
        result = await p.delete_account("any")
        assert result is True
