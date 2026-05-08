"""Pytest fixtures for custom integration tests."""

from __future__ import annotations

import json
from pathlib import Path
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
def mock_market_prices_client() -> Generator[AsyncMock]:
    """Mock AsyncMarketPricesClient for validation."""
    with patch(
        "custom_components.electricityinfo.config_flow.AsyncMarketPricesClient"
    ) as mock:
        client = AsyncMock()
        client.get_schedules = AsyncMock(return_value=[])
        mock.return_value = client
        yield client


@pytest.fixture
def mock_market_prices_client_invalid() -> Generator[AsyncMock]:
    """Mock AsyncMarketPricesClient that raises authentication error."""
    with patch(
        "custom_components.electricityinfo.config_flow.AsyncMarketPricesClient"
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
    fixture_file = Path(__file__).parent / "fixtures" / "market_prices.json"
    with fixture_file.open() as f:
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
    """Mock AsyncMarketPricesClient for sensor platform tests."""
    with patch(
        "custom_components.electricityinfo.coordinator.AsyncMarketPricesClient"
    ) as mock:
        client = AsyncMock()

        async def mock_get_schedule_prices(**kwargs: object) -> list:
            """Return mock prices for given schedule/node."""
            nodes = kwargs.get("nodes") or []
            node = nodes[0].lower() if nodes else ""
            schedule = str(kwargs.get("schedule", "")).lower()
            key = f"{node}_{schedule}"
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

        client.get_schedule_prices = AsyncMock(side_effect=mock_get_schedule_prices)
        mock.return_value = client
        yield client
