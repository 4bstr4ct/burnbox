from unittest.mock import MagicMock

import pytest

from burnbox.account import AccountService, _generate_secure_str
from burnbox.api import APIClient
from burnbox.exceptions import NoDomainsError, TokenError
from burnbox.messages import MessageService, _make_html_parser


class TestGenerateSecureStr:
    def test_default_length(self):
        s = _generate_secure_str()
        assert len(s) == 10

    def test_custom_length(self):
        s = _generate_secure_str(20)
        assert len(s) == 20

    def test_lowercase_and_digits_only(self):
        import string
        allowed = set(string.ascii_lowercase + string.digits)
        s = _generate_secure_str(100)
        assert all(c in allowed for c in s)

    def test_unique_across_calls(self):
        s1 = _generate_secure_str()
        s2 = _generate_secure_str()
        assert s1 != s2


class TestAccountService:
    def _make_api(self, responses: list[dict] | None = None):
        api = MagicMock(spec=APIClient)
        api.token = None
        if responses is not None:
            api.request = MagicMock(side_effect=responses)
        return api

    def test_register_success(self):
        api = self._make_api([
            {"hydra:member": [{"domain": "example.com"}]},
            {"id": "acc_123"},
            {"token": "jwt-abc"},
        ])
        svc = AccountService(api)
        address, password, account_id = svc.register()
        assert address.endswith("@example.com")
        assert password
        assert account_id == "acc_123"
        assert api.token == "jwt-abc"
        assert api.request.call_count == 3

    def test_register_no_domains(self):
        api = self._make_api([{"hydra:member": []}])
        svc = AccountService(api)
        with pytest.raises(NoDomainsError):
            svc.register()

    def test_register_no_token(self):
        api = self._make_api([
            {"hydra:member": [{"domain": "example.com"}]},
            {"id": "acc_123"},
            {"token": None},
        ])
        svc = AccountService(api)
        with pytest.raises(TokenError):
            svc.register()

    def test_register_empty_token(self):
        api = self._make_api([
            {"hydra:member": [{"domain": "example.com"}]},
            {"id": "acc_123"},
            {},
        ])
        svc = AccountService(api)
        with pytest.raises(TokenError):
            svc.register()

    def test_login_success(self):
        api = self._make_api([{"token": "jwt-xyz"}, {"id": "acc_99"}])
        svc = AccountService(api)
        address, account_id = svc.login("user@example.com", "pass123")
        assert address == "user@example.com"
        assert account_id == "acc_99"
        assert svc.account_id == "acc_99"
        assert api.token == "jwt-xyz"

    def test_login_no_token(self):
        api = self._make_api([{}])
        svc = AccountService(api)
        with pytest.raises(TokenError):
            svc.login("user@example.com", "pass123")

    def test_delete_success(self):
        api = self._make_api([{}])
        svc = AccountService(api)
        svc.account_id = "acc_42"
        svc.delete()
        api.request.assert_called_once_with("DELETE", "/accounts/acc_42")

    def test_delete_noop_without_account_id(self):
        api = self._make_api()
        svc = AccountService(api)
        svc.account_id = None
        svc.delete()
        api.request.assert_not_called()


class TestMessageService:
    def _make_api(self, responses: list[dict] | None = None):
        api = MagicMock(spec=APIClient)
        if responses is not None:
            api.request = MagicMock(side_effect=responses)
        return api

    def test_list_previews(self):
        api = self._make_api([{
            "hydra:member": [
                {"id": "m1", "from": {"address": "a@b.com"}, "subject": "Hello"},
                {"id": "m2", "from": {}, "subject": "No From"},
            ]
        }])
        svc = MessageService(api)
        previews = svc.list_previews()
        assert len(previews) == 2
        assert previews[0].id == "m1"
        assert previews[0].sender == "a@b.com"
        assert previews[1].sender == "Unknown Sender"

    def test_list_previews_empty(self):
        api = self._make_api([{"hydra:member": []}])
        svc = MessageService(api)
        assert svc.list_previews() == []

    def test_get_message(self):
        api = self._make_api([{
            "id": "m1",
            "from": {"address": "sender@test.com"},
            "subject": "Test",
            "html": "<p>Body</p>",
            "text": "Body text",
        }])
        svc = MessageService(api)
        msg = svc.get_message("m1")
        assert msg.id == "m1"
        assert msg.sender == "sender@test.com"
        assert msg.subject == "Test"
        assert "Body" in msg.content

    def test_get_message_no_from(self):
        api = self._make_api([{
            "id": "m2",
            "from": {},
            "subject": "No Subject",
            "html": None,
            "text": "Plain",
        }])
        svc = MessageService(api)
        msg = svc.get_message("m2")
        assert msg.sender == "Unknown Sender"
        assert msg.content == "Plain"

    def test_fetch_new_filters_seen(self):
        api = self._make_api([
            {"hydra:member": [
                {"id": "m1", "from": {"address": "a@b"}, "subject": "Old"},
                {"id": "m2", "from": {"address": "c@d"}, "subject": "New"},
            ]},
            {
                "id": "m2",
                "from": {"address": "c@d"},
                "subject": "New",
                "html": None,
                "text": "New body",
            },
        ])
        svc = MessageService(api)
        new_msgs = svc.fetch_new(seen_ids={"m1"})
        assert len(new_msgs) == 1
        assert new_msgs[0].id == "m2"

    def test_fetch_new_all_seen(self):
        api = self._make_api([{
            "hydra:member": [
                {"id": "m1", "from": {"address": "a@b"}, "subject": "Old"},
            ]
        }])
        svc = MessageService(api)
        assert svc.fetch_new(seen_ids={"m1"}) == []

    def test_fetch_new_none_seen(self):
        api = self._make_api([
            {"hydra:member": [
                {"id": "m1", "from": {"address": "a@b"}, "subject": "S1"},
            ]},
            {
                "id": "m1",
                "from": {"address": "a@b"},
                "subject": "S1",
                "html": None,
                "text": "Body",
            },
        ])
        svc = MessageService(api)
        msgs = svc.fetch_new(seen_ids=set())
        assert len(msgs) == 1


class TestMakeHtmlParser:
    def test_parser_config(self):
        parser = _make_html_parser()
        assert parser.ignore_links is False
        assert parser.ignore_images is True
        assert parser.body_width == 0
