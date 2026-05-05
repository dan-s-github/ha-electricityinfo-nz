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


@pytest.fixture
def mock_market_prices() -> dict:
    """Load mock market prices from fixture file."""
    import json
    from pathlib import Path

    fixture_file = Path(__file__).parent / "fixtures" / "market_prices.json"
    with open(fixture_file) as f:
        return json.load(f)


@pytest.fixture
def mock_coordinator() -> AsyncMock:
    """Mock DataUpdateCoordinator for sensor testing."""
    coordinator = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.data = None
    coordinator.last_update_success = True
    coordinator.error = None
    return coordinator


@pytest.fixture
def mock_market_prices_client_sensor(mock_market_prices: dict) -> Generator[AsyncMock]:
    """Mock MarketPricesClient for sensor platform tests."""
    with patch("custom_components.electricityinfo.sensor.MarketPricesClient") as mock:
        client = AsyncMock()

        async def mock_get_schedules(node: str, *args, **kwargs) -> list:
            """Return mock prices for given node."""
            key = f"{node.lower()}_daily_spot"
            if key in mock_market_prices:
                data = mock_market_prices[key]
                return [
                    {
                        "timestamp": data["timestamp"],
                        "confidence_level": data["confidence_level"],
                        "forecast_period": data["forecast_period"],
                        "market_type": data["market_type"],
                        "node": data["node"],
                        "schedule_type": data["schedule_type"],
                        "price_value": data["current_price"],
                        "prices": data.get("prices", [data["current_price"]]),
                    }
                ]
            return []

        client.get_schedules = AsyncMock(side_effect=mock_get_schedules)
        mock.return_value = client
        yield client
