import pytest
from typer.testing import CliRunner
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from burnbox.models import Session, InboxMessage
from burnbox.config import AppConfig
from burnbox.session import SessionStore
from burnbox.client import BurnBoxClient
from burnbox.cli import app


runner = CliRunner()


@pytest.fixture
def mock_provider():
    p = AsyncMock()
    p.name = "mailtm"
    p.is_alive.return_value = True
    p.register.return_value = Session(
        address="test@example.com", account_id="1",
        token="tok", provider_name="mailtm", created_at=0.0,
    )
    p.fetch_messages.return_value = []
    p.delete_account.return_value = True
    return p


class TestVersion:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "burnbox" in result.stdout


class TestAddressCommand:
    @patch("burnbox.cli._build_client")
    def test_address_command(self, mock_build, mock_provider, tmp_path):
        store = SessionStore(dir=tmp_path)
        config = AppConfig(copy_address=False)
        client = BurnBoxClient(provider=mock_provider, session_store=store, config=config)
        mock_build.return_value = (client, mock_provider)

        result = runner.invoke(app, ["address"])
        assert result.exit_code == 0
        assert "test@example.com" in result.stdout


class TestResumeCommand:
    @patch("burnbox.cli._build_client")
    def test_resume_no_session(self, mock_build, mock_provider, tmp_path):
        store = SessionStore(dir=tmp_path)
        config = AppConfig()
        client = BurnBoxClient(provider=mock_provider, session_store=store, config=config)
        mock_build.return_value = (client, mock_provider)

        result = runner.invoke(app, ["resume"])
        assert "No saved session" in result.stdout or result.exit_code != 0
