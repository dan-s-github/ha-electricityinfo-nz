"""Test sensor module for electricityinfo_nz integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import (
    DOMAIN,
    LIVE_PRICE_RESTORE_STALENESS_MINUTES,
)
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator
from custom_components.electricityinfo.sensor import (
    DayAheadForecastSensor,
    IntradayForecastSensor,
    LivePriceSensor,
)
from tests.helpers import create_mock_market_node_subentry


@pytest.fixture(autouse=True)
def mock_coordinator_update():
    """Prevent real API calls by stubbing out the coordinator data fetch."""
    with patch.object(
        ElectricityInfoCoordinator, "_async_update_data", return_value={}
    ):
        yield


# ---------------------------------------------------------------------------
# Existing platform setup test
# ---------------------------------------------------------------------------


async def test_sensor_platform_sets_up(hass) -> None:
    """Test setting up the integration creates market-node sensor entities."""
    subentry = create_mock_market_node_subentry(
        subentry_id="market_node_1",
        title="HAY2201 [c/kWh]",
        node="HAY2201",
        price_unit="c/kWh",
        enable_live_price=True,
        enable_forecast=False,
        enable_accounting=False,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main",
        data={
            "client_id": "test_client",
            "client_secret": "test_secret",
        },
        subentries_data=[
            {
                "data": dict(subentry.data),
                "subentry_type": "market_node",
                "title": subentry.title,
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) >= 1

    price_sensors = [s for s in states if "live_price" in s.entity_id]
    sensor_ids = [s.entity_id for s in states]
    assert len(price_sensors) > 0, f"No price sensors found. States: {sensor_ids}"

    # FR-005: verify device_class for monetary sensors
    for sensor in price_sensors:
        entity = hass.data["entity_components"]["sensor"].get_entity(sensor.entity_id)
        assert entity.device_class == SensorDeviceClass.MONETARY
        assert entity.state_class is None


async def test_sensor_platform_sets_up_accounting_entities(hass) -> None:
    """Accounting setup registers settled, delta, daily, and previous-day sensors."""
    subentry = create_mock_market_node_subentry(
        subentry_id="market_node_1",
        title="HAY2201 [c/kWh]",
        node="HAY2201",
        price_unit="c/kWh",
        enable_live_price=False,
        enable_forecast=False,
        enable_accounting=True,
        import_meter_entity_id="sensor.import_meter",
        export_meter_entity_id="sensor.export_meter",
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main",
        data={
            "client_id": "test_client",
            "client_secret": "test_secret",
        },
        subentries_data=[
            {
                "data": dict(subentry.data),
                "subentry_type": "market_node",
                "title": subentry.title,
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sensor_ids = [state.entity_id for state in hass.states.async_all("sensor")]
    expected_suffixes = [
        "settled_price",
        "import_cost",
        "daily_import_cost",
        "previous_day_import_cost",
        "export_revenue",
        "daily_export_revenue",
        "previous_day_export_revenue",
    ]
    for suffix in expected_suffixes:
        assert any(suffix in entity_id for entity_id in sensor_ids), (
            f"Missing accounting sensor containing '{suffix}'. "
            f"Current sensor IDs: {sensor_ids}"
        )


async def test_live_sensor_uses_coordinator_live_payload(hass, mock_entry) -> None:
    """Live sensor consumes coordinator-provided current period payload."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=True, enable_forecast=False, enable_accounting=False
    )
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)

    def _make_price(dt, period, price) -> MagicMock:
        p = MagicMock()
        p.trading_datetime = dt
        p.trading_period = period
        p.node = "HAY2201"
        p.schedule = "PRSL"
        p.price = price
        return p

    day_ahead = MagicMock()
    day_ahead.prices = [
        _make_price(now - timedelta(minutes=30), 23, 4.05),
        _make_price(now, 24, 4.23),
        _make_price(now + timedelta(minutes=30), 25, 4.51),
    ]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "live_current": {
                    "timestamp": "2026-05-09T12:00:00+00:00",
                    "trading_period": 24,
                    "node": "HAY2201",
                    "schedule": "PRSL",
                    "price": 4.23,
                },
                "day_ahead": day_ahead,
                "error": None,
            }
        }
        entity = LivePriceSensor(coordinator, mock_entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(4.23, abs=1e-6)
    attrs = entity.extra_state_attributes
    assert attrs["trading_period"] == 24
    assert "forecast" not in attrs
    assert "history" not in attrs


async def test_live_sensor_unavailable_when_no_rtd_data(hass, mock_entry) -> None:
    """LivePriceSensor is unavailable when coordinator has no RTD data."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=True, enable_forecast=False, enable_accounting=False
    )

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "live_current": None,
                "rtd": None,
                "day_ahead": None,
                "error": None,
            }
        }
        entity = LivePriceSensor(coordinator, mock_entry, subentry)
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    assert entity.native_value is None
    assert not entity.available


async def test_live_sensor_exposes_rtd_history_attribute(hass, mock_entry) -> None:
    """LivePriceSensor includes history list from RTD back-periods."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=True, enable_forecast=False, enable_accounting=False
    )
    now = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)

    def _make_rtd(dt, period, price) -> MagicMock:
        p = MagicMock()
        p.trading_datetime = dt
        p.trading_period = period
        p.node = "HAY2201"
        p.schedule = "RTD"
        p.price = price
        return p

    rtd = MagicMock()
    rtd.prices = [
        _make_rtd(now - timedelta(minutes=60), 22, 3.50),
        _make_rtd(now - timedelta(minutes=30), 23, 4.05),
        _make_rtd(now, 24, 4.23),
    ]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "live_current": {
                    "timestamp": now.isoformat(),
                    "trading_period": 24,
                    "node": "HAY2201",
                    "schedule": "RTD",
                    "price": 4.23,
                },
                "rtd": rtd,
                "day_ahead": None,
                "error": None,
            }
        }
        entity = LivePriceSensor(coordinator, mock_entry, subentry)
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(4.23)
    attrs = entity.extra_state_attributes
    assert "history" in attrs
    assert len(attrs["history"]) == 3
    assert attrs["history"][0]["trading_period"] == 22
    assert attrs["history"][1]["trading_period"] == 23
    assert attrs["history"][2]["trading_period"] == 24
    assert attrs["history"][2]["schedule"] == "RTD"


async def test_live_sensor_restores_recent_state(hass, mock_entry) -> None:
    """LivePriceSensor restores recent state."""
    subentry = create_mock_market_node_subentry()
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = LivePriceSensor(coordinator, mock_entry, subentry)

        recent_ts = datetime(2026, 5, 9, 11, 30, tzinfo=UTC)
        mock_state = MagicMock()
        mock_state.state = "4.523"
        mock_state.attributes = {"timestamp": recent_ts.isoformat()}

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch(
                "homeassistant.util.dt.utcnow",
                return_value=recent_ts + timedelta(minutes=10),
            ),
        ):
            await entity.async_added_to_hass()

        assert entity.native_value == pytest.approx(4.523, abs=0.001)


async def test_live_sensor_discards_stale_state(hass, mock_entry) -> None:
    """LivePriceSensor drops stale restored state and requests refresh."""
    subentry = create_mock_market_node_subentry()
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = LivePriceSensor(coordinator, mock_entry, subentry)

        stale_ts = datetime(2026, 5, 9, 11, 0, tzinfo=UTC)
        mock_state = MagicMock()
        mock_state.state = "4.523"
        mock_state.attributes = {"timestamp": stale_ts.isoformat()}

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch(
                "homeassistant.util.dt.utcnow",
                return_value=stale_ts + timedelta(minutes=45),
            ),
        ):
            await entity.async_added_to_hass()

        assert entity.native_value is None
        coordinator.async_request_refresh.assert_awaited()
    assert not entity.available


async def test_day_ahead_forecast_sensor_state_and_attributes(hass, mock_entry) -> None:
    """Day-ahead sensor uses current trade period as state and keeps history."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=True,
        forecast_horizons=["day_ahead"],
        forecast_retention_hours=6,
    )
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    def _make_price(dt, period, price) -> MagicMock:
        p = MagicMock()
        p.trading_datetime = dt
        p.trading_period = period
        p.node = "HAY2201"
        p.schedule = "PRSL"
        p.price = price
        return p

    day_ahead = MagicMock()
    day_ahead.prices = [
        _make_price(now - timedelta(minutes=30), 23, 7.0),
        _make_price(now, 24, 8.0),
        _make_price(now + timedelta(minutes=30), 25, 9.0),
        _make_price(now + timedelta(minutes=60), 26, 10.0),
    ]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "day_ahead": day_ahead,
                "intraday": None,
                "accounting": None,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = DayAheadForecastSensor(coordinator, mock_entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(8.0)
    attrs = entity.extra_state_attributes
    # Active period (24) is in history; forecast contains only strictly future periods
    assert [p["trading_period"] for p in attrs["history"]] == [23, 24]
    assert [p["trading_period"] for p in attrs["forecast"]] == [25, 26]


async def test_intraday_forecast_sensor_uses_intraday_schedule(
    hass, mock_entry
) -> None:
    """Intraday sensor reads state from intraday node data."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=True,
        forecast_horizons=["intraday"],
    )
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    def _make_price(dt, period, price) -> MagicMock:
        p = MagicMock()
        p.trading_datetime = dt
        p.trading_period = period
        p.node = "HAY2201"
        p.schedule = "PRSS"
        p.price = price
        return p

    intraday = MagicMock()
    intraday.prices = [
        _make_price(now - timedelta(minutes=30), 23, 5.0),
        _make_price(now + timedelta(minutes=30), 24, 6.0),
        _make_price(now + timedelta(minutes=60), 25, 7.0),
    ]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "day_ahead": None,
                "intraday": intraday,
                "accounting": None,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = IntradayForecastSensor(coordinator, mock_entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(6.0)
    attrs = entity.extra_state_attributes
    # No current period at `now` (gap between 11:30 and 12:30); no change from pre-fix
    assert [p["trading_period"] for p in attrs["forecast"]] == [24, 25]
    assert [p["trading_period"] for p in attrs["history"]] == [23]


async def test_intraday_current_period_in_history_not_forecast(
    hass, mock_entry
) -> None:
    """Active period is in history, not forecast; only future periods in forecast."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=True,
        forecast_horizons=["intraday"],
    )
    current_start = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)
    now = current_start + timedelta(minutes=10)

    def _make_price(dt, period, price) -> MagicMock:
        p = MagicMock()
        p.trading_datetime = dt
        p.trading_period = period
        p.node = "HAY2201"
        p.schedule = "PRSS"
        p.price = price
        return p

    intraday = MagicMock()
    intraday.prices = [
        _make_price(current_start - timedelta(minutes=30), 23, 5.0),
        _make_price(current_start, 24, 6.0),
        _make_price(current_start + timedelta(minutes=30), 25, 7.0),
    ]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "day_ahead": None,
                "intraday": intraday,
                "accounting": None,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = IntradayForecastSensor(coordinator, mock_entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    assert entity.native_value == pytest.approx(6.0)
    attrs = entity.extra_state_attributes
    # Active period (24) is in history; forecast = strictly future (25 only)
    assert [p["trading_period"] for p in attrs["history"]] == [23, 24]
    assert [p["trading_period"] for p in attrs["forecast"]] == [25]


async def test_forecast_sensor_unavailable_when_no_current_or_future_prices(
    hass, mock_entry
) -> None:
    """Forecast sensor is unavailable when schedule has only elapsed periods."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=True,
        forecast_horizons=["day_ahead"],
        forecast_retention_hours=6,
    )
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    past_price = MagicMock()
    past_price.trading_datetime = now - timedelta(minutes=30)
    past_price.trading_period = 23
    past_price.node = "HAY2201"
    past_price.schedule = "PRSL"
    past_price.price = 7.0

    day_ahead = MagicMock()
    day_ahead.prices = [past_price]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "day_ahead": day_ahead,
                "intraday": None,
                "accounting": None,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = DayAheadForecastSensor(coordinator, mock_entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    assert not entity.available
    assert entity.native_value is None


async def test_live_sensor_staleness_guard_threshold_is_30_minutes(
    hass, mock_entry
) -> None:
    """LivePriceSensor staleness guard uses 30-minute threshold, not poll interval."""
    assert LIVE_PRICE_RESTORE_STALENESS_MINUTES == 30

    subentry = create_mock_market_node_subentry()
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = LivePriceSensor(coordinator, mock_entry, subentry)

        base_ts = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
        mock_state = MagicMock()
        mock_state.state = "4.523"
        mock_state.attributes = {"timestamp": base_ts.isoformat()}

        # 29 minutes old — should be restored (not stale)
        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch(
                "homeassistant.util.dt.utcnow",
                return_value=base_ts + timedelta(minutes=29),
            ),
        ):
            await entity.async_added_to_hass()

        assert entity.native_value == pytest.approx(4.523, abs=0.001)

        # 31 minutes old — should be discarded (stale)
        entity2 = LivePriceSensor(coordinator, mock_entry, subentry)
        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity2, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch(
                "homeassistant.util.dt.utcnow",
                return_value=base_ts + timedelta(minutes=31),
            ),
        ):
            await entity2.async_added_to_hass()

        assert entity2.native_value is None
