from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from burnbox.models import Session


@pytest.fixture
def mock_provider():
    p = AsyncMock()
    p.name = "mailtm"
    p.is_alive.return_value = True
    p.register.return_value = Session(
        address="test@example.com", account_id="1",
        token="tok", provider_name="mailtm", created_at=0.0,
    )
    p.fetch_messages.return_value = []
    p.delete_account.return_value = True
    return p


@pytest.fixture
def mock_async_client():
    client = AsyncMock()
    return client
