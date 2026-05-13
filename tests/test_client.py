from unittest.mock import MagicMock, patch

import pytest

from burnbox.account import AccountService
from burnbox.api import APIClient
from burnbox.client import BurnBoxClient, _save_session, _load_session, _delete_session
from burnbox.exceptions import BurnBoxError
from burnbox.messages import MessageService
from burnbox.models import InboxMessage


def _make_client(
    account_return=None,
    login_return=None,
    delete_side_effect=None,
    fetch_new_return=None,
):
    api = MagicMock(spec=APIClient)
    account = MagicMock(spec=AccountService)
    account.account_id = None
    if account_return is not None:
        account.register = MagicMock(return_value=account_return)
    if login_return is not None:
        account.login = MagicMock(return_value=login_return)
    if delete_side_effect is not None:
        account.delete = MagicMock(side_effect=delete_side_effect)
    else:
        account.delete = MagicMock()

    messages = MagicMock(spec=MessageService)
    if fetch_new_return is not None:
        messages.fetch_new = MagicMock(return_value=fetch_new_return)

    client = BurnBoxClient(api=api)
    client._account = account
    client._messages = messages
    return client, account, messages, api


class TestBurnBoxClientRegister:
    def test_register_sets_fields_and_saves(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        client, account, _, _ = _make_client(
            account_return=("user@x.com", "pw123", "acc_1")
        )
        result = client.register()
        assert result == "user@x.com"
        assert client.address == "user@x.com"
        assert client.password == "pw123"
        assert client.account_id == "acc_1"
        assert session_file.exists()


class TestBurnBoxClientLogin:
    def test_login_sets_fields(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        client, account, _, _ = _make_client(login_return=("user@x.com", "acc_1"))
        result = client.login("user@x.com", "pw")
        assert result == "user@x.com"
        assert client.password == "pw"
        assert client.account_id == "acc_1"


class TestBurnBoxClientResume:
    def test_resume_from_session(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        _save_session("user@x.com", "pw", "acc_5")

        client, account, _, _ = _make_client(login_return=("user@x.com", "acc_5"))
        result = client.resume()
        assert result == "user@x.com"
        assert client.account_id == "acc_5"
        assert account.account_id == "acc_5"

    def test_resume_no_session_raises(self, tmp_path, monkeypatch):
        session_file = tmp_path / "nope.json"
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)
        monkeypatch.setattr("burnbox.client.SESSION_DIR", tmp_path)

        client, _, _, _ = _make_client(login_return=("user@x.com", "acc_x"))
        with pytest.raises(BurnBoxError, match="No saved session"):
            client.resume()


class TestBurnBoxClientBurn:
    def test_burn_success(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        client, account, _, _ = _make_client()
        account.account_id = "acc_1"
        assert client.burn() is True
        account.delete.assert_called_once()

    def test_burn_no_account_id_returns_false(self):
        client, account, _, _ = _make_client()
        account.account_id = None
        assert client.burn() is False
        account.delete.assert_not_called()

    def test_burn_error_returns_false(self):
        client, account, _, _ = _make_client(delete_side_effect=BurnBoxError("fail"))
        account.account_id = "acc_1"
        assert client.burn() is False


class TestBurnBoxClientFetchNewMessages:
    def test_delegates_to_message_service(self):
        msg = InboxMessage(id="1", sender="a@b", subject="Hi", content="body")
        client, _, messages, _ = _make_client(fetch_new_return=[msg])
        result = client.fetch_new_messages(seen_ids=set())
        assert result == [msg]


class TestBurnBoxClientContextManager:
    def test_context_manager_closes(self):
        client, _, _, api = _make_client()
        with client:
            pass
        api.close.assert_called_once()
