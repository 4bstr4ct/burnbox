from burnbox.messages import _normalize_content, _make_html_parser


def test_normalize_html_string():
    parser = _make_html_parser()
    result = _normalize_content("<p>Hello</p>", None, parser)
    assert "Hello" in result


def test_normalize_html_list():
    parser = _make_html_parser()
    result = _normalize_content(["<p>Hello</p>", "<p>World</p>"], None, parser)
    assert "Hello" in result
    assert "World" in result


def test_normalize_text_fallback():
    parser = _make_html_parser()
    result = _normalize_content(None, "Plain text", parser)
    assert result == "Plain text"


def test_normalize_empty():
    parser = _make_html_parser()
    result = _normalize_content(None, None, parser)
    assert result == "[Empty Message]"


def test_normalize_empty_whitespace_only():
    parser = _make_html_parser()
    result = _normalize_content("   ", "   ", parser)
    assert result == "[Empty Message]"


def test_normalize_text_list():
    parser = _make_html_parser()
    result = _normalize_content(None, ["Line 1", "Line 2"], parser)
    assert "Line 1" in result
    assert "Line 2" in result
