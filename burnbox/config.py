from __future__ import annotations

import os
import pathlib
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    base_url: str = "https://api.mail.tm"
    request_timeout: float = 10.0
    polling_interval: float = 5.0
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

_DEFAULT_CONFIG_DIR = pathlib.Path.home() / ".config"
_CONFIG_NAME = "burnbox.toml"


@dataclass(frozen=True)
class AppConfig:
    provider_default: str | None = None
    custom_url: str | None = None
    poll_interval: float = 5.0
    timeout: float = 10.0
    copy_address: bool = True
    copy_code: bool = True


def load_config(
    config_path: pathlib.Path | None = None,
) -> AppConfig:
    if config_path is None:
        config_path = _DEFAULT_CONFIG_DIR / _CONFIG_NAME

    data: dict = {}
    if config_path.exists() and tomllib is not None:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

    provider = data.get("provider", {})
    polling = data.get("polling", {})
    output = data.get("output", {})

    return AppConfig(
        provider_default=os.environ.get("BURNBOX_PROVIDER") or provider.get("default"),
        custom_url=os.environ.get("BURNBOX_CUSTOM_URL") or provider.get("custom_url"),
        poll_interval=float(
            os.environ.get("BURNBOX_POLL_INTERVAL") or polling.get("interval", 5.0)
        ),
        timeout=float(
            os.environ.get("BURNBOX_TIMEOUT") or polling.get("timeout", 10.0)
        ),
        copy_address=output.get("copy_address", True),
        copy_code=output.get("copy_code", True),
    )
