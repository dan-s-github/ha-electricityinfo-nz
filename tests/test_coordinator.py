"""Tests for accounting coordinator behavior (US3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from electricityinfo_nz.exceptions import MarketPricesAPIError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator

CLIENT_PATH = "custom_components.electricityinfo.coordinator.AsyncMarketPricesClient"


def _entry_with_market_node(subentry_data: dict) -> MagicMock:
    """Build a mock config entry with one market_node subentry."""
    subentry = SimpleNamespace(
        subentry_id="market_node_1",
        subentry_type="market_node",
        data=subentry_data,
    )
    entry = MagicMock()
    entry.data = {"client_id": "id", "client_secret": "secret"}
    entry.subentries = {"market_node_1": subentry}
    return entry


def _multi_entry_with_market_nodes(subentry_1: dict, subentry_2: dict) -> MagicMock:
    """Build a mock config entry with two market_node subentries."""
    entry = MagicMock()
    entry.data = {"client_id": "id", "client_secret": "secret"}
    entry.subentries = {
        "market_node_1": SimpleNamespace(
            subentry_id="market_node_1",
            subentry_type="market_node",
            data=subentry_1,
        ),
        "market_node_2": SimpleNamespace(
            subentry_id="market_node_2",
            subentry_type="market_node",
            data=subentry_2,
        ),
    }
    return entry


def _make_accounting_schedule(price: float = 0.25) -> SimpleNamespace:
    """Create a minimal Interim schedule with one settled row."""
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    return SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=now - timedelta(minutes=30),
                trading_period=24,
                node="HAY2201",
                price=price,
                schedule="Interim",
                run_type="A",
            )
        ]
    )


@pytest.mark.asyncio
async def test_accounting_fetch_uses_interim_back_48(hass) -> None:
    """Accounting fetch uses Interim back=48 and returns settled fields."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": False,
            "enable_forecast": False,
            "enable_accounting": True,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.side_effect = lambda **_kwargs: (
            _make_accounting_schedule(0.25)
        )
        client_cls.return_value = client
        data = await coordinator._async_update_data()

    kwargs = client.get_schedule_prices.call_args.kwargs
    assert kwargs["schedule"] == "Interim"
    assert kwargs["back"] == 48
    node_data = data["market_node_1"]
    assert node_data["settled_price"] == pytest.approx(0.00025, abs=1e-9)
    assert node_data["settled_trading_period"] == 24


@pytest.mark.asyncio
async def test_accounting_meter_delta_skips_first_poll_then_computes(hass) -> None:
    """First poll has no delta; second poll computes cost/revenue deltas."""
    hass.states.async_set(
        "sensor.import_energy",
        "10.0",
        {"device_class": "energy", "unit_of_measurement": "kWh"},
    )
    hass.states.async_set(
        "sensor.export_energy",
        "5.0",
        {"device_class": "energy", "unit_of_measurement": "kWh"},
    )
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": False,
            "enable_forecast": False,
            "enable_accounting": True,
            "import_meter_entity_id": "sensor.import_energy",
            "export_meter_entity_id": "sensor.export_energy",
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.side_effect = lambda **_kwargs: (
            _make_accounting_schedule(0.25)
        )
        client_cls.return_value = client
        first = await coordinator._async_update_data()

        hass.states.async_set(
            "sensor.import_energy",
            "11.5",
            {"device_class": "energy", "unit_of_measurement": "kWh"},
        )
        hass.states.async_set(
            "sensor.export_energy",
            "5.4",
            {"device_class": "energy", "unit_of_measurement": "kWh"},
        )
        second = await coordinator._async_update_data()

    assert first["market_node_1"]["import_cost_delta"] is None
    assert first["market_node_1"]["export_revenue_delta"] is None
    assert second["market_node_1"]["import_energy_delta"] == pytest.approx(
        1.5, abs=1e-6
    )
    assert second["market_node_1"]["export_energy_delta"] == pytest.approx(
        0.4, abs=1e-6
    )
    assert second["market_node_1"]["import_cost_delta"] == pytest.approx(
        0.000375, abs=1e-9
    )
    assert second["market_node_1"]["export_revenue_delta"] == pytest.approx(
        0.0001, abs=1e-9
    )


@pytest.mark.asyncio
async def test_accounting_bidirectional_and_export_fallback(hass) -> None:
    """Fallback to import meter enables bidirectional signed-delta behavior."""
    hass.states.async_set(
        "sensor.grid_meter",
        "100.0",
        {"device_class": "energy", "unit_of_measurement": "kWh"},
    )
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": False,
            "enable_forecast": False,
            "enable_accounting": True,
            "import_meter_entity_id": "sensor.grid_meter",
            "export_meter_entity_id": "sensor.grid_meter",
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.side_effect = lambda **_kwargs: (
            _make_accounting_schedule(0.5)
        )
        client_cls.return_value = client
        await coordinator._async_update_data()

        hass.states.async_set(
            "sensor.grid_meter",
            "98.0",
            {"device_class": "energy", "unit_of_measurement": "kWh"},
        )
        second = await coordinator._async_update_data()

    node_data = second["market_node_1"]
    assert node_data["import_energy_delta"] == pytest.approx(0.0, abs=1e-6)
    assert node_data["export_energy_delta"] == pytest.approx(2.0, abs=1e-6)
    assert node_data["export_revenue_delta"] == pytest.approx(0.001, abs=1e-9)


@pytest.mark.asyncio
async def test_live_fetch_routes_day_ahead_and_converts_units(hass) -> None:
    """Live-enabled node fetches day-ahead and converts to configured unit."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    mock_schedule = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=now,
                trading_period=24,
                node="HAY2201",
                price=100.0,
                schedule="PRSL",
                run_type="A",
            )
        ]
    )
    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.return_value = mock_schedule
        client_cls.return_value = client
        data = await coordinator._async_update_data()

    kwargs = client.get_schedule_prices.call_args.kwargs
    assert kwargs["schedule"] == "PRSL"
    assert kwargs["forward"] == 48
    assert data["market_node_1"]["day_ahead"].prices[0].price == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_forecast_fetch_uses_retention_back_window(hass) -> None:
    """Forecast-enabled fetch includes retention-derived back and forward windows."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": False,
            "enable_forecast": True,
            "forecast_type": "price_responsive",
            "forecast_horizons": ["day_ahead"],
            "forecast_retention_hours": 12,
            "enable_accounting": False,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.return_value = _make_accounting_schedule(0.25)
        client_cls.return_value = client
        await coordinator._async_update_data()

    assert client.get_schedule_prices.call_count == 1
    kwargs = client.get_schedule_prices.call_args.kwargs
    assert kwargs["schedule"] == "PRSL"
    assert kwargs["forward"] == 48
    assert kwargs["back"] == 24


@pytest.mark.asyncio
async def test_coordinator_retries_with_backoff_on_api_error(hass) -> None:
    """Coordinator increments retries and sets retry interval after API failures."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    with (
        patch.object(
            coordinator, "_ensure_client", side_effect=MarketPricesAPIError("boom")
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()

    assert coordinator._retry_count == 1
    assert coordinator.update_interval == timedelta(minutes=1)


@pytest.mark.asyncio
async def test_multi_node_error_isolated_to_failing_subentry(hass) -> None:
    """One failing market node should not block the other node's update."""
    entry = _multi_entry_with_market_nodes(
        {
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        },
        {
            "node": "BEN2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        },
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    hay_schedule = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=datetime.now(UTC).replace(
                    minute=0, second=0, microsecond=0
                ),
                trading_period=24,
                node="HAY2201",
                price=100.0,
                schedule="PRSL",
                run_type="A",
            )
        ]
    )

    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.side_effect = [
            hay_schedule,
            MarketPricesAPIError("ben failure"),
        ]
        client_cls.return_value = client
        data = await coordinator._async_update_data()

    assert data["market_node_1"]["error"] is None
    assert data["market_node_1"]["day_ahead"].prices[0].node == "HAY2201"
    assert "error" in data["market_node_2"]
