from typer.testing import CliRunner
from unittest.mock import AsyncMock, patch

from burnbox.exceptions import SessionError
from burnbox.cli import app


runner = CliRunner()


class TestVersion:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "burnbox" in result.stdout


class TestAddressCommand:
    @patch("burnbox.cli.commands.select_provider", new_callable=AsyncMock)
    def test_address_command(self, mock_select, mock_provider):
        mock_select.return_value = (mock_provider, [])

        result = runner.invoke(app, ["address"])
        assert result.exit_code == 0
        assert "test@example.com" in result.stdout


class TestResumeCommand:
    @patch("burnbox.cli.commands.BurnBoxClient")
    @patch("burnbox.providers.utils.get_provider_by_name")
    def test_resume_no_session(self, mock_get, mock_client_cls, mock_provider):
        mock_get.return_value = (mock_provider, [])
        mock_client = AsyncMock()
        mock_client.resume.side_effect = SessionError(
            "No saved session found. Run 'burnbox' first."
        )
        mock_client.session = None
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["resume"])
        assert "No saved session" in result.stdout
