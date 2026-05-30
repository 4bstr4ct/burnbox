from unittest.mock import patch, MagicMock

from burnbox.notifications import send_notification


class TestSendNotification:
    def test_send_does_not_crash(self):
        send_notification("burnbox", "Code: 1234")

    def test_linux_notify_send(self):
        with patch("burnbox.notifications._is_linux", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = send_notification("burnbox", "Code: 1234")
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "notify-send" in args

    def test_macos_escaped_quotes(self):
        with patch("burnbox.notifications._is_linux", return_value=False):
            with patch("burnbox.notifications._is_macos", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)
                    result = send_notification('He said "hi"', 'Code: "1234"')
        assert result is True
        call_args = mock_run.call_args[0][0]
        script = call_args[-1]
        assert '\\"' in script

    def test_macos_notify_fail(self):
        with patch("burnbox.notifications._is_linux", return_value=False):
            with patch("burnbox.notifications._is_macos", return_value=True):
                with patch("subprocess.run", side_effect=FileNotFoundError):
                    result = send_notification("burnbox", "test")
        assert result is False

    def test_unsupported_platform(self):
        with patch("burnbox.notifications._is_linux", return_value=False):
            with patch("burnbox.notifications._is_macos", return_value=False):
                assert send_notification("burnbox", "test") is False
