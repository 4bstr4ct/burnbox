import pytest
from burnbox.config import load_config, AppConfig


class TestLoadConfig:
    def test_defaults_no_file(self, tmp_path, monkeypatch):
        for key in ["BURNBOX_PROVIDER", "BURNBOX_CUSTOM_URL", "BURNBOX_POLL_INTERVAL", "BURNBOX_TIMEOUT"]:
            monkeypatch.delenv(key, raising=False)
        cfg = load_config(config_path=tmp_path / "nonexistent.toml")
        assert cfg.provider_default is None
        assert cfg.poll_interval == 5.0
        assert cfg.timeout == 10.0
        assert cfg.copy_address is True
        assert cfg.copy_code is True

    def test_toml_file(self, tmp_path, monkeypatch):
        for key in ["BURNBOX_PROVIDER", "BURNBOX_CUSTOM_URL", "BURNBOX_POLL_INTERVAL", "BURNBOX_TIMEOUT"]:
            monkeypatch.delenv(key, raising=False)
        config_file = tmp_path / "burnbox.toml"
        config_file.write_text("""
[provider]
default = "mailtm"
custom_url = "https://my-mail.example.com"

[polling]
interval = 3.0

[output]
copy_address = false
copy_code = false
""")
        cfg = load_config(config_path=config_file)
        assert cfg.provider_default == "mailtm"
        assert cfg.custom_url == "https://my-mail.example.com"
        assert cfg.poll_interval == 3.0
        assert cfg.copy_address is False
        assert cfg.copy_code is False

    def test_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BURNBOX_PROVIDER", "guerrillamail")
        monkeypatch.setenv("BURNBOX_POLL_INTERVAL", "2.0")
        cfg = load_config(config_path=tmp_path / "nonexistent.toml")
        assert cfg.provider_default == "guerrillamail"
        assert cfg.poll_interval == 2.0

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        for key in ["BURNBOX_PROVIDER", "BURNBOX_CUSTOM_URL", "BURNBOX_POLL_INTERVAL", "BURNBOX_TIMEOUT"]:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("BURNBOX_PROVIDER", "guerrillamail")
        config_file = tmp_path / "burnbox.toml"
        config_file.write_text('[provider]\ndefault = "mailtm"\n')
        cfg = load_config(config_path=config_file)
        assert cfg.provider_default == "guerrillamail"

    def test_appconfig_frozen(self):
        cfg = AppConfig()
        with pytest.raises(AttributeError):
            cfg.poll_interval = 99.0
