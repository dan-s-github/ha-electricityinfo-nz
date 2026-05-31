"""Tests for accounting coordinator behavior (US3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from electricityinfo_nz.exceptions import MarketPricesAPIError
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.electricityinfo.const import UPDATE_INTERVAL_MINUTES
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
async def test_accounting_fetch_uses_interim_back_from_config(hass) -> None:
    """Accounting fetch back uses Interim schedule derived from retention config."""
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
    assert kwargs["back"] == 48  # default 24h retention = 48 periods
    node_data = data["market_node_1"]
    assert node_data["settled_price"] == pytest.approx(0.00025, abs=1e-9)
    assert node_data["settled_trading_period"] == 24


@pytest.mark.asyncio
async def test_accounting_fetch_back_scales_with_retention_hours(hass) -> None:
    """Accounting fetch back scales with accounting_retention_hours config."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": False,
            "enable_forecast": False,
            "enable_accounting": True,
            "accounting_retention_hours": 48,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.side_effect = lambda **_kwargs: (
            _make_accounting_schedule(0.25)
        )
        client_cls.return_value = client
        await coordinator._async_update_data()

    kwargs = client.get_schedule_prices.call_args.kwargs
    assert kwargs["schedule"] == "Interim"
    assert kwargs["back"] == 96  # 48h retention = 96 periods


@pytest.mark.asyncio
async def test_accounting_metrics_select_current_period_over_future(hass) -> None:
    """Accounting settled metrics prefer current period over future rows."""
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
    now = datetime(2026, 5, 24, 12, 10, tzinfo=UTC)
    accounting = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=datetime(2026, 5, 24, 11, 30, tzinfo=UTC),
                trading_period=23,
                node="HAY2201",
                price=0.20,
                schedule="Interim",
                run_type="A",
            ),
            SimpleNamespace(
                trading_datetime=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
                trading_period=24,
                node="HAY2201",
                price=0.25,
                schedule="Interim",
                run_type="A",
            ),
            SimpleNamespace(
                trading_datetime=datetime(2026, 5, 24, 12, 30, tzinfo=UTC),
                trading_period=25,
                node="HAY2201",
                price=0.30,
                schedule="Interim",
                run_type="A",
            ),
        ]
    )
    node_data = {"accounting": accounting}
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        coordinator._populate_accounting_metrics(
            subentry_id="market_node_1",
            config={"import_meter_entity_id": None, "export_meter_entity_id": None},
            node_data=node_data,
        )

    assert node_data["settled_price"] == pytest.approx(0.25, abs=1e-9)
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
async def test_live_fetch_uses_rtd_schedule(hass) -> None:
    """Live-enabled node fetches RTD schedule and populates live_current."""
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
    mock_rtd = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=now,
                trading_period=24,
                node="HAY2201",
                price=100.0,
                schedule="RTD",
                run_type="A",
            )
        ]
    )
    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.return_value = mock_rtd
        client_cls.return_value = client
        data = await coordinator._async_update_data()

    kwargs = client.get_schedule_prices.call_args.kwargs
    assert kwargs["schedule"] == "RTD"
    assert "forward" not in kwargs
    assert data["market_node_1"]["live_current"]["schedule"] == "RTD"
    assert data["market_node_1"]["day_ahead"] is None


@pytest.mark.asyncio
async def test_live_fetch_picks_most_recent_rtd_period(hass) -> None:
    """live_current picks the most recently dispatched RTD period, not the oldest."""
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

    now = datetime.now(UTC).replace(second=0, microsecond=0)
    mock_rtd = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=now - timedelta(minutes=15),
                trading_period=32,
                node="HAY2201",
                price=10.0,
                schedule="RTD",
                run_type="A",
            ),
            SimpleNamespace(
                trading_datetime=now - timedelta(minutes=10),
                trading_period=32,
                node="HAY2201",
                price=12.0,
                schedule="RTD",
                run_type="A",
            ),
            SimpleNamespace(
                trading_datetime=now - timedelta(minutes=5),
                trading_period=32,
                node="HAY2201",
                price=14.0,
                schedule="RTD",
                run_type="A",
            ),
        ]
    )
    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.return_value = mock_rtd
        client_cls.return_value = client
        data = await coordinator._async_update_data()

    live = data["market_node_1"]["live_current"]
    # API prices are NZD/MWh; 14.0 * 0.1 = 1.4 c/kWh after conversion
    assert live["price"] == pytest.approx(1.4)
    assert live["trading_period"] == 32


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
async def test_intraday_fetch_back_derived_from_forecast_retention(hass) -> None:
    """Intraday fetch back window is derived from forecast_retention_hours config."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": False,
            "enable_forecast": True,
            "forecast_type": "price_responsive",
            "forecast_horizons": ["intraday"],
            "forecast_retention_hours": 24,
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
    assert kwargs["schedule"] == "PRSS"
    assert kwargs["forward"] == 8  # intraday forward is always 8 periods
    assert kwargs["back"] == 48  # 24h retention = 48 periods


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
                schedule="RTD",
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
    assert data["market_node_1"]["live_current"]["node"] == "HAY2201"
    assert "error" in data["market_node_2"]


@pytest.mark.asyncio
async def test_coordinator_default_update_interval(hass) -> None:
    """Coordinator update interval defaults to 5 minutes."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": False,
            "enable_forecast": False,
            "enable_accounting": False,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)
    assert coordinator.update_interval == timedelta(minutes=UPDATE_INTERVAL_MINUTES)
    assert UPDATE_INTERVAL_MINUTES == 5


@pytest.mark.asyncio
async def test_live_and_forecast_enabled_makes_two_api_calls(hass) -> None:
    """When both live and forecast are enabled, coordinator makes two API calls."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": True,
            "forecast_type": "price_responsive",
            "forecast_horizons": ["day_ahead"],
            "forecast_retention_hours": 6,
            "enable_accounting": False,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    mock_response = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=now,
                trading_period=24,
                node="HAY2201",
                price=100.0,
                schedule="RTD",
                run_type="A",
            )
        ]
    )
    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.return_value = mock_response
        client_cls.return_value = client
        await coordinator._async_update_data()

    assert client.get_schedule_prices.call_count == 2
    schedules = [
        c.kwargs["schedule"] for c in client.get_schedule_prices.call_args_list
    ]
    assert "RTD" in schedules
    assert "PRSL" in schedules


@pytest.mark.asyncio
async def test_forecast_only_does_not_call_rtd(hass) -> None:
    """When only forecast is enabled (no live), coordinator does not call RTD."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": False,
            "enable_forecast": True,
            "forecast_type": "price_responsive",
            "forecast_horizons": ["day_ahead"],
            "forecast_retention_hours": 6,
            "enable_accounting": False,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    mock_response = SimpleNamespace(
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
        client.get_schedule_prices.return_value = mock_response
        client_cls.return_value = client
        data = await coordinator._async_update_data()

    assert client.get_schedule_prices.call_count == 1
    kwargs = client.get_schedule_prices.call_args.kwargs
    assert kwargs["schedule"] == "PRSL"
    assert data["market_node_1"]["live_current"] is None


@pytest.mark.asyncio
async def test_rtd_failure_does_not_abort_forecast_fetch(hass) -> None:
    """RTD API failure leaves live_current None but does not prevent forecast fetch."""
    entry = _entry_with_market_node(
        {
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": True,
            "forecast_type": "price_responsive",
            "forecast_horizons": ["day_ahead"],
            "forecast_retention_hours": 6,
            "enable_accounting": False,
        }
    )
    coordinator = ElectricityInfoCoordinator(hass, entry)

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    mock_forecast = SimpleNamespace(
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

    def _side_effect(**kwargs) -> SimpleNamespace:
        if kwargs.get("schedule") == "RTD":
            msg = "RTD unavailable"
            raise MarketPricesAPIError(msg)
        return mock_forecast

    with patch(CLIENT_PATH) as client_cls:
        client = AsyncMock()
        client.get_schedule_prices.side_effect = _side_effect
        client_cls.return_value = client
        data = await coordinator._async_update_data()

    assert data["market_node_1"]["live_current"] is None
    assert data["market_node_1"]["rtd"] is None
    assert data["market_node_1"]["day_ahead"] is not None
