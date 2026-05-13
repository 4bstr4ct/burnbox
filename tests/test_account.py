import json
import pathlib
import tempfile

from burnbox.account import _generate_password, _PASSWORD_LEN, _MIN_PASSWORD_LEN
from burnbox.client import _save_session, _load_session, _delete_session, SESSION_FILE


class TestGeneratePassword:
    def test_default_length(self):
        pw = _generate_password()
        assert len(pw) == _PASSWORD_LEN

    def test_has_lowercase(self):
        pw = _generate_password()
        assert any(c.islower() for c in pw)

    def test_has_uppercase(self):
        pw = _generate_password()
        assert any(c.isupper() for c in pw)

    def test_has_digit(self):
        pw = _generate_password()
        assert any(c.isdigit() for c in pw)

    def test_has_special(self):
        pw = _generate_password()
        assert any(c in "!@#$%&*" for c in pw)

    def test_custom_length(self):
        pw = _generate_password(20)
        assert len(pw) == 20

    def test_minimum_length(self):
        pw = _generate_password(8)
        assert len(pw) == 8

    def test_too_short_raises(self):
        try:
            _generate_password(7)
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_unique_across_calls(self):
        pw1 = _generate_password()
        pw2 = _generate_password()
        assert pw1 != pw2


class TestSessionIO:
    def test_save_and_load(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        _save_session("test@example.com", "secret123", "acc_42")
        loaded = _load_session()
        assert loaded is not None
        assert loaded["address"] == "test@example.com"
        assert loaded["password"] == "secret123"
        assert loaded["account_id"] == "acc_42"

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        session_file = tmp_path / "nope.json"
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)
        monkeypatch.setattr("burnbox.client.SESSION_DIR", tmp_path)
        assert _load_session() is None

    def test_load_corrupt_json(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_dir.mkdir()
        session_file = session_dir / "session.json"
        session_file.write_text("not json{{{", encoding="utf-8")
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)
        assert _load_session() is None

    def test_delete_session(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        _save_session("a@b", "pw", "id1")
        assert session_file.exists()
        _delete_session()
        assert not session_file.exists()

    def test_delete_nonexistent_no_error(self, tmp_path, monkeypatch):
        session_file = tmp_path / "nope.json"
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)
        _delete_session()

    def test_save_without_account_id(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        _save_session("a@b", "pw", None)
        loaded = _load_session()
        assert loaded is not None
        assert "account_id" not in loaded

    def test_session_file_permissions(self, tmp_path, monkeypatch):
        session_dir = tmp_path / "burnbox"
        session_file = session_dir / "session.json"
        monkeypatch.setattr("burnbox.client.SESSION_DIR", session_dir)
        monkeypatch.setattr("burnbox.client.SESSION_FILE", session_file)

        _save_session("a@b", "pw", "id1")
        import stat
        mode = session_file.stat().st_mode & 0o777
        assert mode == 0o600
