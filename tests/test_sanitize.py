import pytest
from burnbox.providers.sanitize import safe_path_segment
from burnbox.exceptions import APIError


class TestSafePathSegment:
    def test_valid_id(self):
        assert safe_path_segment("abc123") == "abc123"

    def test_empty_rejected(self):
        with pytest.raises(APIError, match="empty"):
            safe_path_segment("")

    def test_dotdot_rejected(self):
        with pytest.raises(APIError, match="Invalid"):
            safe_path_segment("..")

    def test_slash_rejected(self):
        with pytest.raises(APIError, match="Invalid"):
            safe_path_segment("abc/123")

    def test_backslash_rejected(self):
        with pytest.raises(APIError, match="Invalid"):
            safe_path_segment("abc\\123")

    def test_traversal_rejected(self):
        with pytest.raises(APIError, match="Invalid"):
            safe_path_segment("../etc/passwd")
