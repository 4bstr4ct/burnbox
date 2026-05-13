class BurnBoxError(Exception):
    """Base exception for all burnbox errors."""


class APIError(BurnBoxError):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


class NoDomainsError(BurnBoxError):
    """Raised when no domains are available."""


class TokenError(BurnBoxError):
    """Raised when token acquisition fails."""


class AuthExpiredError(BurnBoxError):
    """Raised when the auth token has expired (401)."""


class SessionError(BurnBoxError):
    """Raised when session operations fail."""


class ProviderError(BurnBoxError):
    """Raised when provider operations fail."""
