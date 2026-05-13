from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    base_url: str = "https://api.mail.tm"
    request_timeout: float = 10.0
    polling_interval: float = 5.0
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0
