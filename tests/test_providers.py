import pytest
from unittest.mock import AsyncMock, MagicMock
from burnbox.providers.base import Provider
from burnbox.models import Session
from burnbox.providers.dropmail import DropMailProvider
from burnbox.providers.guerrillamail import GuerrillaMailProvider
from burnbox.providers.mailgw import MailGwProvider
from burnbox.providers.mailtm import MailTmProvider
from burnbox.exceptions import AuthExpiredError, NoDomainsError, ProviderError


@pytest.fixture
def mock_async_client():
    client = AsyncMock()
    return client


class TestSession:
    def test_session_fields(self):
        s = Session(
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

    def test_session_frozen(self):
        s = Session(
            address="a@b.c", account_id="1", token="t",
            provider_name="mailtm", created_at=0.0,
        )
        with pytest.raises(AttributeError):
            s.address = "new"

    def test_session_repr_masks_token(self):
        s = Session(address="a@b.c", account_id="1", token="secret123",
                     provider_name="mailtm", created_at=0.0)
        r = repr(s)
        assert "secret123" not in r
        assert "***" in r


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
        assert isinstance(session, Session)
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


class TestDropMailProvider:
    def test_name(self):
        p = DropMailProvider()
        assert p.name == "dropmail"

    def test_supports_custom_url(self):
        p = DropMailProvider()
        assert p.supports_custom_url is False

    @pytest.mark.asyncio
    async def test_is_alive_success(self, mock_async_client):
        graphql_resp = MagicMock()
        graphql_resp.json.return_value = {
            "data": {"domains": [{"id": "RG9tYWluOjE="}]}
        }
        graphql_resp.raise_for_status = MagicMock()
        mock_async_client.post = AsyncMock(return_value=graphql_resp)
        p = DropMailProvider(client=mock_async_client)
        assert await p.is_alive() is True

    @pytest.mark.asyncio
    async def test_is_alive_failure(self, mock_async_client):
        mock_async_client.post.side_effect = Exception("connection error")
        p = DropMailProvider(client=mock_async_client)
        assert await p.is_alive() is False

    @pytest.mark.asyncio
    async def test_register(self, mock_async_client):
        graphql_resp = MagicMock()
        graphql_resp.json.return_value = {
            "data": {
                "introduceSession": {
                    "id": "U2Vzc2lvbjoxMjM=",
                    "expiresAt": "2026-05-30T05:00:00+00:00",
                    "addresses": [{"address": "test@dropmail.me"}],
                }
            }
        }
        graphql_resp.raise_for_status = MagicMock()
        mock_async_client.post = AsyncMock(return_value=graphql_resp)
        p = DropMailProvider(client=mock_async_client)
        session = await p.register()
        assert isinstance(session, Session)
        assert session.address.endswith("@dropmail.me")
        assert session.provider_name == "dropmail"
        assert session.token == "U2Vzc2lvbjoxMjM="

    @pytest.mark.asyncio
    async def test_register_no_address(self, mock_async_client):
        graphql_resp = MagicMock()
        graphql_resp.json.return_value = {
            "data": {"introduceSession": {"id": "abc", "addresses": []}}
        }
        graphql_resp.raise_for_status = MagicMock()
        mock_async_client.post = AsyncMock(return_value=graphql_resp)
        p = DropMailProvider(client=mock_async_client)
        with pytest.raises(NoDomainsError, match="no address"):
            await p.register()

    @pytest.mark.asyncio
    async def test_fetch_messages(self, mock_async_client):
        p = DropMailProvider(client=mock_async_client)
        p._session_id = "U2Vzc2lvbjoxMjM="

        graphql_resp = MagicMock()
        graphql_resp.json.return_value = {
            "data": {
                "session": {
                    "mails": [
                        {
                            "id": "msg1",
                            "fromAddr": "sender@test.com",
                            "headerSubject": "Hello",
                            "text": "Your code is 9999",
                            "html": None,
                        }
                    ]
                }
            }
        }
        graphql_resp.raise_for_status = MagicMock()
        mock_async_client.post = AsyncMock(return_value=graphql_resp)
        messages = await p.fetch_messages(seen_ids=set())
        assert len(messages) == 1
        assert messages[0].sender == "sender@test.com"
        assert "9999" in messages[0].content

    @pytest.mark.asyncio
    async def test_fetch_messages_filters_seen(self, mock_async_client):
        p = DropMailProvider(client=mock_async_client)
        p._session_id = "U2Vzc2lvbjoxMjM="

        graphql_resp = MagicMock()
        graphql_resp.json.return_value = {
            "data": {
                "session": {
                    "mails": [
                        {"id": "msg1", "fromAddr": "a@b.c", "headerSubject": "Old", "text": "old", "html": None},
                        {"id": "msg2", "fromAddr": "c@d.c", "headerSubject": "New", "text": "new", "html": None},
                    ]
                }
            }
        }
        graphql_resp.raise_for_status = MagicMock()
        mock_async_client.post = AsyncMock(return_value=graphql_resp)
        messages = await p.fetch_messages(seen_ids={"msg1"})
        assert len(messages) == 1
        assert messages[0].id == "msg2"

    @pytest.mark.asyncio
    async def test_fetch_messages_not_registered(self, mock_async_client):
        p = DropMailProvider(client=mock_async_client)
        with pytest.raises(AuthExpiredError, match="not registered"):
            await p.fetch_messages(seen_ids=set())

    @pytest.mark.asyncio
    async def test_fetch_messages_session_expired(self, mock_async_client):
        p = DropMailProvider(client=mock_async_client)
        p._session_id = "expired-id"

        graphql_resp = MagicMock()
        graphql_resp.json.return_value = {
            "data": {"session": None},
            "errors": [{"extensions": {"code": "SESSION_NOT_FOUND"}, "message": "session_not_found"}],
        }
        graphql_resp.raise_for_status = MagicMock()
        mock_async_client.post = AsyncMock(return_value=graphql_resp)
        with pytest.raises(AuthExpiredError, match="session expired"):
            await p.fetch_messages(seen_ids=set())

    @pytest.mark.asyncio
    async def test_delete_always_true(self, mock_async_client):
        p = DropMailProvider(client=mock_async_client)
        result = await p.delete_account("any")
        assert result is True

    @pytest.mark.asyncio
    async def test_restore(self, mock_async_client):
        p = DropMailProvider(client=mock_async_client)
        session = Session(
            address="test@dropmail.me", account_id="sid1",
            token="sid1", provider_name="dropmail", created_at=0.0,
        )
        await p.restore(session)
        assert p._session_id == "sid1"
        assert p._address == "test@dropmail.me"

    def test_provider_protocol_compliance(self):
        p = DropMailProvider()
        assert isinstance(p, Provider)

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_async_client):
        mock_async_client.aclose = AsyncMock()
        p = DropMailProvider(client=mock_async_client)
        async with p:
            pass
        mock_async_client.aclose.assert_called_once()


class TestGuerrillaMailProvider:
    def test_name(self):
        p = GuerrillaMailProvider()
        assert p.name == "guerrillamail"

    def test_supports_custom_url(self):
        p = GuerrillaMailProvider()
        assert p.supports_custom_url is False

    @pytest.mark.asyncio
    async def test_is_alive_success(self, mock_async_client):
        addr_resp = MagicMock()
        addr_resp.json.return_value = {"email_addr": "test@sharklasers.com", "sid_token": "abc"}
        addr_resp.raise_for_status = MagicMock()
        mock_async_client.get = AsyncMock(return_value=addr_resp)
        p = GuerrillaMailProvider(client=mock_async_client)
        assert await p.is_alive() is True

    @pytest.mark.asyncio
    async def test_is_alive_failure(self, mock_async_client):
        mock_async_client.get.side_effect = Exception("connection error")
        p = GuerrillaMailProvider(client=mock_async_client)
        assert await p.is_alive() is False

    @pytest.mark.asyncio
    async def test_register(self, mock_async_client):
        get_addr_resp = MagicMock()
        get_addr_resp.json.return_value = {
            "email_addr": "random@grr.la",
            "sid_token": "sid123",
        }
        get_addr_resp.raise_for_status = MagicMock()

        set_user_resp = MagicMock()
        set_user_resp.json.return_value = {
            "email_addr": "abc12345@sharklasers.com",
            "sid_token": "sid123",
        }
        set_user_resp.raise_for_status = MagicMock()

        mock_async_client.get = AsyncMock(side_effect=[get_addr_resp, set_user_resp])
        p = GuerrillaMailProvider(client=mock_async_client)
        session = await p.register()
        assert isinstance(session, Session)
        assert session.address.endswith("@sharklasers.com")
        assert session.account_id == "sid123"
        assert session.token == "sid123"
        assert session.provider_name == "guerrillamail"

    @pytest.mark.asyncio
    async def test_register_no_sid_token(self, mock_async_client):
        addr_resp = MagicMock()
        addr_resp.json.return_value = {"email_addr": "x@y.z"}
        addr_resp.raise_for_status = MagicMock()
        mock_async_client.get = AsyncMock(return_value=addr_resp)
        p = GuerrillaMailProvider(client=mock_async_client)
        with pytest.raises(ProviderError, match="sid_token"):
            await p.register()

    @pytest.mark.asyncio
    async def test_fetch_messages(self, mock_async_client):
        p = GuerrillaMailProvider(client=mock_async_client)
        p._sid_token = "sid123"
        p._address = "test@sharklasers.com"

        check_resp = MagicMock()
        check_resp.json.return_value = {
            "list": [
                {"mail_id": 1, "mail_from": "sender@test.com", "mail_subject": "Hello"},
            ]
        }
        check_resp.raise_for_status = MagicMock()

        fetch_resp = MagicMock()
        fetch_resp.json.return_value = {
            "mail_body": "<p>Your code is 5678</p>",
            "mail_excerpt": "Your code is...",
        }
        fetch_resp.raise_for_status = MagicMock()

        mock_async_client.get = AsyncMock(side_effect=[check_resp, fetch_resp])
        messages = await p.fetch_messages(seen_ids=set())
        assert len(messages) == 1
        assert messages[0].sender == "sender@test.com"
        assert "5678" in messages[0].content

    @pytest.mark.asyncio
    async def test_fetch_messages_filters_seen(self, mock_async_client):
        p = GuerrillaMailProvider(client=mock_async_client)
        p._sid_token = "sid123"
        p._address = "test@sharklasers.com"

        check_resp = MagicMock()
        check_resp.json.return_value = {
            "list": [
                {"mail_id": 1, "mail_from": "a@b.c", "mail_subject": "Old"},
                {"mail_id": 2, "mail_from": "c@d.c", "mail_subject": "New"},
            ]
        }
        check_resp.raise_for_status = MagicMock()

        fetch_resp = MagicMock()
        fetch_resp.json.return_value = {
            "mail_body": "New message text",
            "mail_excerpt": "New...",
        }
        fetch_resp.raise_for_status = MagicMock()

        mock_async_client.get = AsyncMock(side_effect=[check_resp, fetch_resp])
        messages = await p.fetch_messages(seen_ids={"1"})
        assert len(messages) == 1
        assert messages[0].id == "2"

    @pytest.mark.asyncio
    async def test_fetch_messages_not_registered(self, mock_async_client):
        p = GuerrillaMailProvider(client=mock_async_client)
        with pytest.raises(ProviderError, match="not registered"):
            await p.fetch_messages(seen_ids=set())

    @pytest.mark.asyncio
    async def test_delete_account(self, mock_async_client):
        forget_resp = MagicMock()
        forget_resp.json.return_value = {"success": True}
        forget_resp.raise_for_status = MagicMock()
        mock_async_client.get = AsyncMock(return_value=forget_resp)
        p = GuerrillaMailProvider(client=mock_async_client)
        p._address = "test@sharklasers.com"
        result = await p.delete_account("sid123")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_account_failure(self, mock_async_client):
        mock_async_client.get.side_effect = Exception("network error")
        p = GuerrillaMailProvider(client=mock_async_client)
        p._address = "test@sharklasers.com"
        result = await p.delete_account("sid123")
        assert result is False

    def test_provider_protocol_compliance(self):
        p = GuerrillaMailProvider()
        assert isinstance(p, Provider)

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_async_client):
        mock_async_client.aclose = AsyncMock()
        p = GuerrillaMailProvider(client=mock_async_client)
        async with p:
            pass
        mock_async_client.aclose.assert_called_once()
