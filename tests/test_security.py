import pytest
from burnbox.security import validate_url
from burnbox.exceptions import BurnBoxError


class TestValidateUrl:
    def test_https_allowed(self):
        assert validate_url("https://api.example.com") == "https://api.example.com"

    def test_http_allowed(self):
        assert validate_url("http://example.com") == "http://example.com"

    def test_ftp_rejected(self):
        with pytest.raises(BurnBoxError, match="scheme"):
            validate_url("ftp://example.com")

    def test_no_hostname_rejected(self):
        with pytest.raises(BurnBoxError, match="no hostname"):
            validate_url("https://")

    def test_localhost_http_allowed(self):
        assert validate_url("http://localhost:3000") == "http://localhost:3000"

    def test_localhost_https_rejected(self):
        with pytest.raises(BurnBoxError, match="loopback"):
            validate_url("https://localhost")

    def test_loopback_127_allowed(self):
        assert validate_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"

    def test_loopback_127_https_rejected(self):
        with pytest.raises(BurnBoxError, match="loopback"):
            validate_url("https://127.0.0.1")

    def test_private_ip_rejected(self):
        with pytest.raises(BurnBoxError, match="private"):
            validate_url("https://192.168.1.1")

    def test_10_network_rejected(self):
        with pytest.raises(BurnBoxError, match="private"):
            validate_url("https://10.0.0.1")

    def test_link_local_rejected(self):
        with pytest.raises(BurnBoxError, match="private"):
            validate_url("https://169.254.1.1")

    def test_reserved_rejected(self):
        with pytest.raises(BurnBoxError, match="reserved"):
            validate_url("https://0.0.0.0")

    def test_public_ip_allowed(self):
        assert validate_url("https://1.1.1.1") == "https://1.1.1.1"

    def test_domain_name_allowed(self):
        assert validate_url("https://api.mail.tm") == "https://api.mail.tm"

    def test_custom_label(self):
        with pytest.raises(BurnBoxError, match="custom_url"):
            validate_url("ftp://x", label="custom_url")
