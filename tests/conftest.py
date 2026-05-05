"""Pytest fixtures for custom integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from electricityinfo_nz.exceptions import AuthenticationError

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading integrations from custom_components in tests."""


@pytest.fixture
def mock_oauth_credentials() -> Generator[AsyncMock]:
    """Mock OAuth2ClientCredentials for testing."""
    with patch(
        "custom_components.electricityinfo.config_flow.OAuth2ClientCredentials"
    ) as mock:
        oauth = AsyncMock()
        oauth.get_token = AsyncMock(return_value="test_token_123")
        mock.return_value = oauth
        yield oauth


@pytest.fixture
def mock_market_prices_client() -> Generator[AsyncMock]:
    """Mock MarketPricesClient for validation."""
    with patch(
        "custom_components.electricityinfo.config_flow.MarketPricesClient"
    ) as mock:
        client = AsyncMock()
        client.get_schedules = AsyncMock(return_value=[])
        mock.return_value = client
        yield client


@pytest.fixture
def mock_market_prices_client_invalid() -> Generator[AsyncMock]:
    """Mock MarketPricesClient that raises authentication error."""
    with patch(
        "custom_components.electricityinfo.config_flow.MarketPricesClient"
    ) as mock:
        client = AsyncMock()
        client.get_schedules = AsyncMock(
            side_effect=AuthenticationError("Invalid token")
        )
        mock.return_value = client
        yield client
