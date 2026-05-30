from burnbox.api import BurnBox, Message, create
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

__version__ = "1.0.0"

__all__ = [
    "BurnBox",
    "BurnBoxClient",
    "Message",
    "AppConfig",
    "load_config",
    "create",
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
