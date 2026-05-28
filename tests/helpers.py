"""Helper utilities for sensor platform tests."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigSubentry


def create_mock_subentry(
    subentry_id: str = "test_subentry_01",
    title: str = "Test Sensor",
    schedule_type: str = "RTD",
    market_type: str = "E",
    node: str = "HAY2201",
    forward_prices_count: int = 24,
    name: str | None = None,
) -> ConfigSubentry:
    """Create a mock ConfigSubentry for a price sensor."""
    data: dict[str, Any] = {
        "schedule_type": schedule_type,
        "market_type": market_type,
        "node": node,
        "forward_prices_count": forward_prices_count,
    }
    if name:
        data["name"] = name
    return ConfigSubentry(
        data=MappingProxyType(data),
        subentry_id=subentry_id,
        subentry_type="sensor",
        title=title,
        unique_id=None,
    )


def create_mock_market_node_subentry(
    subentry_id: str = "market_node_01",
    title: str = "HAY2201 [c/kWh]",
    node: str = "HAY2201",
    price_unit: str = "c/kWh",
    enable_live_price: bool = True,
    enable_forecast: bool = False,
    forecast_type: str = "price_responsive",
    forecast_horizons: list[str] | None = None,
    forecast_retention_hours: int = 24,
    enable_accounting: bool = False,
    accounting_retention_hours: int = 24,
    import_meter_entity_id: str | None = None,
    export_meter_entity_id: str | None = None,
) -> ConfigSubentry:
    """Create a mock ConfigSubentry for a market node."""
    data: dict[str, Any] = {
        "node": node,
        "price_unit": price_unit,
        "enable_live_price": enable_live_price,
        "enable_forecast": enable_forecast,
        "enable_accounting": enable_accounting,
    }
    if enable_forecast:
        data["forecast_type"] = forecast_type
        data["forecast_horizons"] = forecast_horizons or ["day_ahead"]
        data["forecast_retention_hours"] = forecast_retention_hours
    if enable_accounting:
        data["accounting_retention_hours"] = accounting_retention_hours
        data["import_meter_entity_id"] = import_meter_entity_id
        data["export_meter_entity_id"] = (
            export_meter_entity_id or import_meter_entity_id
        )

    return ConfigSubentry(
        data=MappingProxyType(data),
        subentry_id=subentry_id,
        subentry_type="market_node",
        title=title,
        unique_id=None,
    )


def create_mock_price_response(
    node: str = "HAY2201",
    schedule_type: str = "RTD",
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
    coordinator = AsyncMock()
    coordinator.data = data or {}
    coordinator.last_update_success = last_update_success
    coordinator.error = error
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


def create_market_node_config(
    node: str = "HAY2201",
    price_unit: str = "c/kWh",
    enable_live_price: bool = True,
    enable_forecast: bool = False,
    forecast_type: str = "price_responsive",
    forecast_horizons: list[str] | None = None,
    forecast_retention_hours: int = 24,
    enable_accounting: bool = False,
    accounting_retention_hours: int = 24,
    import_meter_entity_id: str | None = None,
    export_meter_entity_id: str | None = None,
) -> dict[str, Any]:
    """Build normalized market-node config payloads for tests."""
    data: dict[str, Any] = {
        "node": node,
        "price_unit": price_unit,
        "enable_live_price": enable_live_price,
        "enable_forecast": enable_forecast,
        "enable_accounting": enable_accounting,
    }
    if enable_forecast:
        data["forecast_type"] = forecast_type
        data["forecast_horizons"] = forecast_horizons or ["day_ahead"]
        data["forecast_retention_hours"] = forecast_retention_hours
    if enable_accounting:
        data["accounting_retention_hours"] = accounting_retention_hours
        data["import_meter_entity_id"] = import_meter_entity_id
        data["export_meter_entity_id"] = export_meter_entity_id
    return data


def create_mock_node_data(
    schedule: str = "PRSL",
    node: str = "HAY2201",
    price: float = 4.23,
    trading_period: int = 24,
    trading_datetime: str = "2026-05-09T12:00:00+00:00",
    error: str | None = None,
) -> dict[str, Any]:
    """Build coordinator node payload for one subentry."""
    price_detail = {
        "trading_datetime": trading_datetime,
        "trading_period": trading_period,
        "node": node,
        "price": price,
    }
    return {
        "day_ahead": {
            "schedule": schedule,
            "schedule_name": "Mock schedule",
            "prices": [price_detail],
        },
        "intraday": None,
        "accounting": None,
        "import_cost_delta": None,
        "export_revenue_delta": None,
        "accounting_date_nzt": None,
        "config": {"node": node},
        "error": error,
    }


def create_mock_entity_id(
    node: str = "HAY2201",
    schedule_type: str = "RTD",
    market_type: str = "E",
    unit: str = "NZD/MWh",
) -> str:
    """Create expected entity ID for a sensor."""
    unit_suffix = unit.replace("/", "_").lower()
    return (
        f"sensor.electricityinfo_nz_{node.lower()}"
        f"_{schedule_type.lower()}_{market_type.lower()}_{unit_suffix}"
    )
