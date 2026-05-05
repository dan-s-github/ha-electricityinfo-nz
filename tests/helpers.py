"""Helper utilities for sensor platform tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from unittest.mock import AsyncMock


def create_mock_sensor_config(
    sensor_id: str = "test_sensor",
    schedule_type: str = "daily_spot",
    market_type: str = "energy",
    node: str = "NEA",
    forward_prices_count: int = 24,
    unit_preference: str = "NZD/MWh",
) -> dict[str, Any]:
    """Create a mock sensor configuration."""
    return {
        "id": sensor_id,
        "schedule_type": schedule_type,
        "market_type": market_type,
        "node": node,
        "forward_prices_count": forward_prices_count,
        "unit_preference": unit_preference,
    }


def create_mock_price_response(
    node: str = "NEA",
    schedule_type: str = "daily_spot",
    market_type: str = "energy",
    current_price: float = 45.23,
    prices_count: int = 24,
) -> dict[str, Any]:
    """Create a mock API price response."""
    prices = [current_price + (i * 0.5) for i in range(prices_count)]
    return {
        "timestamp": "2026-05-05T17:30:00Z",
        "confidence_level": 0.95,
        "forecast_period": "24h" if prices_count == 24 else "7d",
        "market_type": market_type,
        "node": node,
        "schedule_type": schedule_type,
        "price_value": current_price,
        "prices": prices,
    }


def create_mock_coordinator(
    data: dict[str, Any] | None = None,
    last_update_success: bool = True,
    error: str | None = None,
) -> AsyncMock:
    """Create a mock DataUpdateCoordinator."""
    from unittest.mock import AsyncMock

    coordinator = AsyncMock()
    coordinator.data = data or {}
    coordinator.last_update_success = last_update_success
    coordinator.error = error
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def create_mock_entity_id(
    node: str = "NEA",
    schedule_type: str = "daily_spot",
    market_type: str = "energy",
    unit: str = "NZD/MWh",
) -> str:
    """Create expected entity ID for a sensor."""
    unit_suffix = unit.replace("/", "_").lower()
    return f"sensor.electricityinfo_nz_{node.lower()}_{schedule_type}_{market_type}_{unit_suffix}"


def create_mock_unique_id(
    config_entry_id: str = "test_config_123",
    sensor_id: str = "test_sensor",
) -> str:
    """Create expected unique ID for a sensor."""
    return f"electricityinfo_nz_{config_entry_id}_{sensor_id}"
