import json
import pytest
from dataclasses import asdict
from burnbox.models import Session
from burnbox.session import SessionStore


class TestSession:
    def test_fields(self):
        s = Session(
            address="a@b.c",
            account_id="1",
            token="tok",
            provider_name="mailtm",
            created_at=100.0,
        )
        assert s.address == "a@b.c"
        assert s.account_id == "1"

    def test_frozen(self):
        s = Session(
            address="a@b.c", account_id="1", token="tok", provider_name="mailtm", created_at=100.0
        )
        with pytest.raises(AttributeError):
            s.address = "x"

    def test_repr_masks_token(self):
        s = Session(
            address="a@b.c",
            account_id="1",
            token="secret123",
            provider_name="mailtm",
            created_at=100.0,
        )
        r = repr(s)
        assert "secret123" not in r
        assert "***" in r

    def test_repr_empty_token(self):
        s = Session(
            address="a@b.c",
            account_id="1",
            token="",
            provider_name="guerrillamail",
            created_at=100.0,
        )
        r = repr(s)
        assert "(empty)" in r

    def test_asdict(self):
        s = Session(
            address="a@b.c", account_id="1", token="tok", provider_name="mailtm", created_at=100.0
        )
        d = asdict(s)
        assert d["address"] == "a@b.c"
        assert d["provider_name"] == "mailtm"


class TestSessionStore:
    def test_save_and_load(self, tmp_path):
        store = SessionStore(store_dir=tmp_path)
        s = Session(
            address="a@b.c", account_id="1", token="tok", provider_name="mailtm", created_at=100.0
        )
        store.save(s)
        loaded = store.load()
        assert loaded is not None
        assert loaded.address == "a@b.c"
        assert loaded.token == "tok"
        assert loaded.provider_name == "mailtm"

    def test_load_missing_returns_none(self, tmp_path):
        store = SessionStore(store_dir=tmp_path)
        assert store.load() is None

    def test_delete(self, tmp_path):
        store = SessionStore(store_dir=tmp_path)
        s = Session(
            address="a@b.c", account_id="1", token="tok", provider_name="mailtm", created_at=100.0
        )
        store.save(s)
        store.delete()
        assert store.load() is None

    def test_file_permissions(self, tmp_path):
        store = SessionStore(store_dir=tmp_path)
        s = Session(
            address="a@b.c", account_id="1", token="tok", provider_name="mailtm", created_at=100.0
        )
        store.save(s)
        mode = (tmp_path / "session.json").stat().st_mode & 0o777
        assert mode == 0o600

    def test_no_password_in_saved_file(self, tmp_path):
        store = SessionStore(store_dir=tmp_path)
        s = Session(
            address="a@b.c", account_id="1", token="tok", provider_name="mailtm", created_at=100.0
        )
        store.save(s)
        data = json.loads((tmp_path / "session.json").read_text())
        assert "password" not in data

    def test_load_corrupt_json(self, tmp_path):
        (tmp_path / "session.json").write_text("not json{{{")
        store = SessionStore(store_dir=tmp_path)
        assert store.load() is None

    def test_load_missing_required_keys(self, tmp_path):
        (tmp_path / "session.json").write_text(json.dumps({"address": "x@y.z"}))
        store = SessionStore(store_dir=tmp_path)
        assert store.load() is None

    def test_atomic_write_no_partial(self, tmp_path):
        store = SessionStore(store_dir=tmp_path)
        s = Session(
            address="a@b.c", account_id="1", token="tok", provider_name="mailtm", created_at=100.0
        )
        store.save(s)
        assert not (tmp_path / "session.tmp").exists()
        assert (tmp_path / "session.json").exists()
