from __future__ import annotations

import math
import os
import pathlib
import sys
from dataclasses import dataclass

from typing import Any

from burnbox.exceptions import BurnBoxError
from burnbox.security import validate_url

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

_DEFAULT_CONFIG_DIR = pathlib.Path.home() / ".config"
_CONFIG_NAME = "burnbox.toml"
_MIN_POLL_INTERVAL = 0.5
_MIN_TIMEOUT = 1.0


def _validate_url(url: str) -> str:
    return validate_url(url, label="BURNBOX_CUSTOM_URL")


def _safe_float(env_var: str, env_val: str | None, toml_val: float, minimum: float) -> float:
    raw = env_val
    if raw:
        try:
            val = float(raw)
        except ValueError:
            raise BurnBoxError(f"Invalid {env_var}={raw!r}: expected a number")
    else:
        val = float(toml_val)
    if not math.isfinite(val):
        raise BurnBoxError(f"Invalid {env_var}={val}: must be a finite number")
    if val < minimum:
        raise BurnBoxError(f"{env_var}={val}: must be >= {minimum}")
    return val


@dataclass(frozen=True)
class AppConfig:
    provider_default: str | None = None
    custom_url: str | None = None
    poll_interval: float = 5.0
    timeout: float = 10.0
    copy_address: bool = True
    copy_code: bool = True
    notifications: bool = True


def load_config(
    config_path: pathlib.Path | None = None,
) -> AppConfig:
    if config_path is None:
        config_path = _DEFAULT_CONFIG_DIR / _CONFIG_NAME

    data: dict[str, Any] = {}
    if config_path.exists() and tomllib is not None:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

    provider = data.get("provider", {})
    polling = data.get("polling", {})
    output = data.get("output", {})

    custom_url_raw = os.environ.get("BURNBOX_CUSTOM_URL") or provider.get("custom_url")
    custom_url = _validate_url(custom_url_raw) if custom_url_raw else None

    return AppConfig(
        provider_default=os.environ.get("BURNBOX_PROVIDER") or provider.get("default"),
        custom_url=custom_url,
        poll_interval=_safe_float(
            "BURNBOX_POLL_INTERVAL",
            os.environ.get("BURNBOX_POLL_INTERVAL"),
            polling.get("interval", 5.0),
            _MIN_POLL_INTERVAL,
        ),
        timeout=_safe_float(
            "BURNBOX_TIMEOUT",
            os.environ.get("BURNBOX_TIMEOUT"),
            polling.get("timeout", 10.0),
            _MIN_TIMEOUT,
        ),
        copy_address=output.get("copy_address", True),
        copy_code=output.get("copy_code", True),
        notifications=output.get("notifications", True),
    )
