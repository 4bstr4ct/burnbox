from burnbox.client import BurnBoxClient
from burnbox.config import AppConfig, load_config
from burnbox.exceptions import (
    APIError,
    AuthExpiredError,
    BurnBoxError,
    NoDomainsError,
    ProviderError,
    SessionError,
    TokenError,
)
from burnbox.models import InboxMessage, MessagePreview, Session

__version__ = "2.0.0"

__all__ = [
    "BurnBoxClient",
    "AppConfig",
    "load_config",
    "BurnBoxError",
    "Session",
    "InboxMessage",
    "MessagePreview",
    "APIError",
    "NoDomainsError",
    "ProviderError",
    "SessionError",
    "TokenError",
    "AuthExpiredError",
]
