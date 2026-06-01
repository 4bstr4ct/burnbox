import pytest
from unittest.mock import patch, MagicMock

from burnbox.detectors import detect_codes, detect_links, extract_best_code, CodeMatch, MessageContext
from burnbox.detectors.engine import ParserEngine
from burnbox.detectors.parsers.alphanumeric_otp import AlphanumericOtpParser
from burnbox.detectors.parsers.labeled_otp import LabeledOtpParser
from burnbox.detectors.parsers.numeric_otp import NumericOtpParser
from burnbox.detectors.parsers.url_code import UrlCodeParser
from burnbox.detectors.parsers.reset_link import ResetLinkParser


class TestCodeMatch:
    def test_frozen(self):
        m = CodeMatch(value="1234", start=0, end=4, kind="labeled_otp", source_parser="X", confidence=0.9)
        with pytest.raises(AttributeError):
            m.value = "5678"

    def test_fields(self):
        m = CodeMatch(value="1234", start=10, end=14, kind="labeled_otp", source_parser="LabeledOtpParser", confidence=0.9)
        assert m.value == "1234"
        assert m.kind == "labeled_otp"
        assert m.confidence == 0.9
        assert m.source_parser == "LabeledOtpParser"


class TestMessageContext:
    def test_defaults(self):
        ctx = MessageContext()
        assert ctx.sender == ""
        assert ctx.subject == ""

    def test_custom(self):
        ctx = MessageContext(sender="a@b.c", subject="Verify")
        assert ctx.sender == "a@b.c"
        assert ctx.subject == "Verify"


class TestLabeledOtpParser:
    def test_en_code(self):
        p = LabeledOtpParser()
        result = p.parse("Your code: 1234", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "1234"
        assert result[0].kind == "labeled_otp"
        assert result[0].confidence == 0.9

    def test_en_verification_code(self):
        p = LabeledOtpParser()
        result = p.parse("Your verification code: 8472", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "8472"

    def test_ru_code(self):
        p = LabeledOtpParser()
        result = p.parse("Ваш код: 5531", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "5531"

    def test_de_code(self):
        p = LabeledOtpParser()
        result = p.parse("Ihr Bestätigungscode: 9921", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "9921"

    def test_fr_code(self):
        p = LabeledOtpParser()
        result = p.parse("Votre code de vérification: 4412", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "4412"

    def test_zh_code(self):
        p = LabeledOtpParser()
        result = p.parse("您的验证码: 6677", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "6677"

    def test_ja_code(self):
        p = LabeledOtpParser()
        result = p.parse("認証コード: 3354", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "3354"

    def test_no_match(self):
        p = LabeledOtpParser()
        result = p.parse("Hello, how are you?", MessageContext())
        assert len(result) == 0

    def test_dedup(self):
        p = LabeledOtpParser()
        result = p.parse("code: 1234 code: 1234", MessageContext())
        values = [m.value for m in result]
        assert values.count("1234") == 1


class TestNumericOtpParser:
    def test_standalone_digits(self):
        p = NumericOtpParser()
        result = p.parse("Here is 8472 for you", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "8472"
        assert result[0].kind == "numeric_otp"

    def test_context_boost_from_text(self):
        p = NumericOtpParser()
        result = p.parse("Please verify your account. Code: 8472", MessageContext())
        numeric = [m for m in result if m.source_parser == "NumericOtpParser"]
        if numeric:
            assert numeric[0].confidence > 0.3

    def test_context_boost_from_subject(self):
        p = NumericOtpParser()
        result = p.parse("Use 8472", MessageContext(sender="a@b.c", subject="Verify your account"))
        numeric = [m for m in result if m.source_parser == "NumericOtpParser"]
        if numeric:
            assert numeric[0].confidence > 0.3

    def test_base_confidence_no_context(self):
        p = NumericOtpParser()
        result = p.parse("The number 8472 appeared", MessageContext(subject="Random stuff"))
        numeric = [m for m in result if m.source_parser == "NumericOtpParser"]
        if numeric:
            assert numeric[0].confidence == 0.3

    def test_no_match(self):
        p = NumericOtpParser()
        result = p.parse("Hello world", MessageContext())
        assert len(result) == 0


class TestUrlCodeParser:
    def test_code_param(self):
        p = UrlCodeParser()
        result = p.parse("Click https://example.com/verify?code=abc123", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "abc123"
        assert result[0].kind == "url_code"

    def test_otp_param(self):
        p = UrlCodeParser()
        result = p.parse("Use https://app.com/login?otp=4455", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "4455"

    def test_token_param(self):
        p = UrlCodeParser()
        result = p.parse("https://service.com/confirm?token=s3cr3t", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "s3cr3t"

    def test_no_code_param(self):
        p = UrlCodeParser()
        result = p.parse("Click https://example.com/page?name=test", MessageContext())
        assert len(result) == 0

    def test_invalid_value_skipped(self):
        p = UrlCodeParser()
        result = p.parse("https://x.com/?code=!@#$%", MessageContext())
        assert len(result) == 0


class TestResetLinkParser:
    def test_verify_link(self):
        p = ResetLinkParser()
        result = p.parse("Click https://example.com/verify?uid=1", MessageContext())
        assert len(result) >= 1
        assert result[0].kind == "reset_link"

    def test_reset_link(self):
        p = ResetLinkParser()
        result = p.parse("Reset: https://app.com/password-reset?email=x", MessageContext())
        assert len(result) >= 1
        assert result[0].kind == "reset_link"

    def test_activate_link(self):
        p = ResetLinkParser()
        result = p.parse("Activate: https://service.com/activate?token=abc", MessageContext())
        assert len(result) >= 1

    def test_normal_link_not_matched(self):
        p = ResetLinkParser()
        result = p.parse("Visit https://example.com/about", MessageContext())
        assert len(result) == 0

    def test_subject_boost(self):
        p = ResetLinkParser()
        r1 = p.parse("https://example.com/verify?x=1", MessageContext(subject="Verify your email"))
        r2 = p.parse("https://example.com/verify?x=1", MessageContext(subject="Hello"))
        assert len(r1) >= 1 and len(r2) >= 1
        assert r1[0].confidence >= r2[0].confidence


class TestParserEngine:
    def test_simple_otp(self):
        result = detect_codes("Your code is 1234")
        assert len(result) >= 1
        assert any(m.value == "1234" for m in result)

    def test_labeled_takes_priority_over_numeric(self):
        result = detect_codes("code: 1234 and also 1234")
        values = [m.value for m in result]
        assert values.count("1234") == 1

    def test_url_code_and_labeled(self):
        result = detect_codes("code: 4455 https://x.com/verify?code=4455")
        values = [m.value for m in result]
        assert "4455" in values

    def test_no_codes(self):
        result = detect_codes("Hello, how are you?")
        assert len(result) == 0

    def test_multiple_distinct_codes(self):
        result = detect_codes("Order #45821 confirmed. Code: 8472")
        assert len(result) >= 2

    def test_best_code_single(self):
        codes = detect_codes("code: 1234")
        best = extract_best_code(codes)
        assert best == "1234"

    def test_best_code_multiple_prefers_highest_confidence(self):
        engine = ParserEngine()
        high = CodeMatch(value="1234", start=0, end=4, kind="labeled_otp", source_parser="LabeledOtpParser", confidence=0.9)
        low = CodeMatch(value="5678", start=10, end=14, kind="numeric_otp", source_parser="NumericOtpParser", confidence=0.3)
        best = engine.best_code([low, high])
        assert best is not None
        assert best.value == "1234"

    def test_best_code_skips_reset_links(self):
        engine = ParserEngine()
        link = CodeMatch(value="https://x.com/reset", start=0, end=22, kind="reset_link", source_parser="ResetLinkParser", confidence=0.7)
        code = CodeMatch(value="1234", start=0, end=4, kind="numeric_otp", source_parser="NumericOtpParser", confidence=0.3)
        best = engine.best_code([link, code])
        assert best is not None
        assert best.value == "1234"

    def test_best_code_only_reset_links(self):
        engine = ParserEngine()
        link = CodeMatch(value="https://x.com/reset", start=0, end=22, kind="reset_link", source_parser="ResetLinkParser", confidence=0.7)
        best = engine.best_code([link])
        assert best is not None
        assert best.kind == "reset_link"

    def test_best_code_empty(self):
        engine = ParserEngine()
        assert engine.best_code([]) is None

    def test_context_propagation(self):
        result = detect_codes("Use 8472", MessageContext(sender="security@github.com", subject="Verify"))
        numeric = [m for m in result if m.kind == "numeric_otp"]
        if numeric:
            assert numeric[0].confidence > 0.3

    def test_custom_parsers(self):
        mock_parser = MagicMock()
        mock_parser.name = "mock"
        mock_parser.priority = 1
        mock_parser.parse.return_value = [
            CodeMatch(value="999", start=0, end=3, kind="mock", source_parser="mock", confidence=1.0)
        ]
        engine = ParserEngine(parsers=[mock_parser])
        result = engine.parse("anything", MessageContext())
        assert len(result) == 1
        assert result[0].value == "999"


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
    def test_single_code_returns_value(self):
        codes = detect_codes("code: 1234")
        result = extract_best_code(codes)
        assert result == "1234"

    def test_no_codes_returns_none(self):
        result = extract_best_code([])
        assert result is None


class TestCopyToClipboard:
    def test_does_not_crash(self):
        from burnbox.detectors import copy_to_clipboard
        copy_to_clipboard("test")

    def test_fallback_to_subprocess(self):
        with patch.dict("sys.modules", {"pyperclip": None}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                from burnbox.detectors.clipboard import copy_to_clipboard
                result = copy_to_clipboard("test")
        assert result is True


class TestAlphanumericOtpParser:
    def test_recovery_code_labeled(self):
        p = AlphanumericOtpParser()
        result = p.parse("Your recovery code: A1B2C3D4", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "A1B2C3D4"
        assert result[0].kind == "alphanumeric_otp"

    def test_backup_key_labeled(self):
        p = AlphanumericOtpParser()
        result = p.parse("Backup key: X9Y8Z7W6", MessageContext())
        assert len(result) >= 1
        assert result[0].value == "X9Y8Z7W6"

    def test_dash_separated_code(self):
        p = AlphanumericOtpParser()
        result = p.parse("Code: A1B2-C3D4-E5F6", MessageContext())
        assert len(result) >= 1
        assert "A1B2-C3D4-E5F6" in result[0].value

    def test_no_match(self):
        p = AlphanumericOtpParser()
        result = p.parse("Hello world", MessageContext())
        assert len(result) == 0
