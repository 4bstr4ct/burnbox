import pytest
from typer.testing import CliRunner
from unittest.mock import AsyncMock, patch

from burnbox.models import Session
from burnbox.exceptions import SessionError
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
    @patch("burnbox.cli._select_provider")
    def test_address_command(self, mock_select, mock_provider):
        mock_select.return_value = (mock_provider, [])

        result = runner.invoke(app, ["address"])
        assert result.exit_code == 0
        assert "test@example.com" in result.stdout


class TestResumeCommand:
    @patch("burnbox.cli.BurnBoxClient")
    @patch("burnbox.cli._get_provider_by_name")
    def test_resume_no_session(self, mock_get, mock_client_cls, mock_provider):
        mock_get.return_value = (mock_provider, [])
        mock_client = AsyncMock()
        mock_client.resume.side_effect = SessionError("No saved session found. Run 'burnbox' first.")
        mock_client.session = None
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["resume"])
        assert "No saved session" in result.stdout
