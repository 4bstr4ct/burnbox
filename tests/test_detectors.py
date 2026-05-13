import pytest
from unittest.mock import patch, MagicMock
from burnbox.detectors import detect_codes, detect_links, extract_best_code, CodeMatch


class TestDetectCodes:
    def test_simple_otp(self):
        result = detect_codes("Your code is 1234")
        assert len(result) >= 1
        assert any(m.value == "1234" for m in result)

    def test_labeled_code_en(self):
        result = detect_codes("Your verification code: 8472")
        assert len(result) >= 1
        assert any(m.value == "8472" and m.kind == "labeled" for m in result)

    def test_labeled_code_ru(self):
        result = detect_codes("Ваш код: 5531")
        assert len(result) >= 1
        assert any(m.value == "5531" and m.kind == "labeled" for m in result)

    def test_multiple_codes(self):
        result = detect_codes("Order #45821 confirmed. Code: 8472")
        assert len(result) >= 2

    def test_no_codes(self):
        result = detect_codes("Hello, how are you?")
        assert len(result) == 0

    def test_labeled_takes_priority(self):
        result = detect_codes("code: 1234 and also 1234")
        values = [m.value for m in result]
        assert values.count("1234") == 1

    def test_code_match_frozen(self):
        m = CodeMatch(value="1234", start=0, end=4, kind="otp")
        with pytest.raises(AttributeError):
            m.value = "5678"


class TestDetectLinks:
    def test_https_link(self):
        result = detect_links("Click https://example.com/verify?token=abc")
        assert len(result) == 1
        assert "https://example.com" in result[0]

    def test_no_links(self):
        result = detect_links("Just plain text here")
        assert len(result) == 0

    def test_multiple_links(self):
        result = detect_links("Go to https://a.com and http://b.com")
        assert len(result) == 2


class TestExtractBestCode:
    def test_single_code_copies(self):
        codes = [CodeMatch(value="1234", start=10, end=14, kind="labeled")]
        with patch("burnbox.detectors.copy_to_clipboard") as mock_copy:
            result = extract_best_code(codes)
        assert result == "1234"
        mock_copy.assert_called_once_with("1234")

    def test_multiple_codes_no_copy(self):
        codes = [
            CodeMatch(value="1234", start=0, end=4, kind="labeled"),
            CodeMatch(value="5678", start=10, end=14, kind="otp"),
        ]
        with patch("burnbox.detectors.copy_to_clipboard") as mock_copy:
            result = extract_best_code(codes)
        assert result is None
        mock_copy.assert_not_called()

    def test_no_codes(self):
        with patch("burnbox.detectors.copy_to_clipboard") as mock_copy:
            result = extract_best_code([])
        assert result is None
        mock_copy.assert_not_called()


class TestCopyToClipboard:
    def test_does_not_crash(self):
        from burnbox.detectors import copy_to_clipboard
        copy_to_clipboard("test")

    def test_fallback_to_xclip(self):
        with patch.dict("sys.modules", {"pyperclip": None}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                from burnbox.detectors import copy_to_clipboard
                result = copy_to_clipboard("test")
        assert result is True
