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
    NZD_PER_MWH_TO_C_PER_KWH,
)
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator
from custom_components.electricityinfo.sensor import (
    DayAheadForecastSensor,
    IntradayForecastSensor,
    LivePriceSensor,
    PriceSensorEntity,
)
from tests.helpers import create_mock_market_node_subentry, create_mock_subentry


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


async def test_live_sensor_fallback_splits_forecast_and_history_by_now(
    hass, mock_entry
) -> None:
    """Fallback day-ahead parsing sets only current-period live attributes."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=True, enable_forecast=False, enable_accounting=False
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
        _make_price(now - timedelta(minutes=60), 22, 7.0),
        _make_price(now - timedelta(minutes=30), 23, 8.0),
        _make_price(now + timedelta(minutes=30), 25, 9.0),
        _make_price(now + timedelta(minutes=60), 26, 10.0),
    ]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "day_ahead": day_ahead,
                "live_current": None,
                "error": None,
            }
        }
        entity = LivePriceSensor(coordinator, mock_entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    attrs = entity.extra_state_attributes
    assert entity.native_value == pytest.approx(8.0)
    assert attrs["trading_period"] == 23
    assert "forecast" not in attrs
    assert "history" not in attrs


# ---------------------------------------------------------------------------
# T050 - Restore-state regression tests (SC-008)
# ---------------------------------------------------------------------------


async def test_available_false_before_restore_and_no_coordinator_data(
    hass, mock_entry
) -> None:
    """Entity is unavailable when coordinator.data is None and no state was restored."""
    subentry = create_mock_subentry()
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")

        # No restored value yet
        assert not entity.available


async def test_available_true_with_restored_value_no_coordinator_data(
    hass, mock_entry
) -> None:
    """
    SC-008: entity is available after restore even when coordinator.data is None.

    This test is RED before T049 fix: the available property currently returns
    False whenever coordinator.data is falsy, blocking restored state from surfacing.
    """
    subentry = create_mock_subentry()
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")

        # Simulate successful state restore
        entity._native_value = 45.23

        # Should be available (SC-008 requirement) — FAILS before T049 fix
        assert entity.available
        assert entity.native_value == pytest.approx(45.23, abs=0.001)


async def test_nzd_restored_state_preserves_native_value(hass, mock_entry) -> None:
    """async_added_to_hass restores _native_value directly for NZD/MWh entities."""
    subentry = create_mock_subentry()
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")

        mock_state = MagicMock()
        mock_state.state = "45.23"
        mock_state.attributes = {}

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
        ):
            await entity.async_added_to_hass()

        assert entity._native_value == pytest.approx(45.23, abs=0.001)
        assert entity.native_value == pytest.approx(45.23, abs=0.001)


async def test_ckwh_restored_state_back_converts_to_canonical_nzd(
    hass, mock_entry
) -> None:
    """c/kWh entity back-converts restored display value to canonical NZD/MWh."""
    subentry = create_mock_subentry()
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="c/kWh")

        # c/kWh display value: 4.523 → internal NZD/MWh = 4.523 * 10 = 45.23
        mock_state = MagicMock()
        mock_state.state = "4.523"
        mock_state.attributes = {}

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
        ):
            await entity.async_added_to_hass()

        assert entity._native_value == pytest.approx(45.23, abs=0.001)
        assert entity.native_value == pytest.approx(
            45.23 * NZD_PER_MWH_TO_C_PER_KWH, abs=0.001
        )


# ---------------------------------------------------------------------------
# T053 - Dual-unit update synchronisation
# ---------------------------------------------------------------------------


def _make_mock_schedule(price: float = 45.23) -> MagicMock:
    """Return a mock schedule object with a single price entry."""
    mock_price = MagicMock()
    mock_price.trading_datetime = datetime(2026, 5, 9, 17, 30, tzinfo=UTC)
    mock_price.trading_period = 35
    mock_price.node = "HAY2201"
    mock_price.schedule = "RTD"
    mock_price.run_type = "actual"
    mock_price.price = price
    mock_schedule = MagicMock()
    mock_schedule.prices = [mock_price]
    return mock_schedule


async def test_dual_unit_entities_reflect_same_data_after_coordinator_update(
    hass, mock_entry
) -> None:
    """NZD/MWh and c/kWh entities update in lockstep when coordinator fires (T053)."""
    subentry = create_mock_subentry()
    mock_schedule = _make_mock_schedule(45.23)

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "prices": mock_schedule,
                "config": dict(subentry.data),
            }
        }

        entity_nzd = PriceSensorEntity(
            coordinator, mock_entry, subentry, unit="NZD/MWh"
        )
        entity_ckwh = PriceSensorEntity(coordinator, mock_entry, subentry, unit="c/kWh")

        with patch.object(entity_nzd, "async_write_ha_state", MagicMock()):
            entity_nzd._handle_coordinator_update()
        with patch.object(entity_ckwh, "async_write_ha_state", MagicMock()):
            entity_ckwh._handle_coordinator_update()

        # Both derive from the same internal NZD/MWh value
        assert entity_nzd._native_value == entity_ckwh._native_value
        assert entity_nzd.native_value == pytest.approx(45.23, abs=0.001)
        assert entity_ckwh.native_value == pytest.approx(
            45.23 * NZD_PER_MWH_TO_C_PER_KWH, abs=0.001
        )


# ---------------------------------------------------------------------------
# T054 / T061 - forecast attribute shape (updated from prices_array)
# ---------------------------------------------------------------------------


async def test_forecast_contains_period_start_and_price_keys(hass, mock_entry) -> None:
    """Forecast elements have period_start and price keys (T054, updated by T061)."""
    subentry = create_mock_subentry()
    mock_price1 = MagicMock()
    mock_price1.trading_datetime = datetime(2026, 5, 9, 17, 30, tzinfo=UTC)
    mock_price1.trading_period = 35
    mock_price1.node = "HAY2201"
    mock_price1.schedule = "RTD"
    mock_price1.run_type = "actual"
    mock_price1.price = 45.23

    mock_price2 = MagicMock()
    mock_price2.trading_datetime = datetime(2026, 5, 9, 18, 0, tzinfo=UTC)
    mock_price2.trading_period = 36
    mock_price2.node = "HAY2201"
    mock_price2.schedule = "RTD"
    mock_price2.run_type = "actual"
    mock_price2.price = 47.11

    mock_schedule = MagicMock()
    mock_schedule.prices = [mock_price1, mock_price2]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "prices": mock_schedule,
                "config": dict(subentry.data),
            }
        }

        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

        attrs = entity.extra_state_attributes
        assert "forecast" in attrs
        assert "prices_array" not in attrs

        forecast = attrs["forecast"]
        assert len(forecast) == 1  # only the future period (price2); price1 is state

        for item in forecast:
            assert "period_start" in item
            assert "price" in item
            assert isinstance(item["period_start"], str)
            assert "T" in item["period_start"]
            assert isinstance(item["price"], float)

        # price1 (45.23) is the current period → state value, not in forecast
        assert forecast[0]["price"] == pytest.approx(47.11, abs=0.001)


async def test_ckwh_forecast_converts_price_field(hass, mock_entry) -> None:
    """c/kWh entity forecast prices are NZD/MWh x 0.1 (T054, updated by T061, T070)."""
    subentry = create_mock_subentry()

    # Need 2 prices: index 0 = state (current), index 1 = forecast[0] (future)
    mock_price0 = MagicMock()
    mock_price0.trading_datetime = datetime(2026, 5, 9, 17, 30, tzinfo=UTC)
    mock_price0.trading_period = 35
    mock_price0.node = "HAY2201"
    mock_price0.schedule = "RTD"
    mock_price0.run_type = "actual"
    mock_price0.price = 45.23  # current period → state

    mock_price1 = MagicMock()
    mock_price1.trading_datetime = datetime(2026, 5, 9, 18, 0, tzinfo=UTC)
    mock_price1.trading_period = 36
    mock_price1.node = "HAY2201"
    mock_price1.schedule = "RTD"
    mock_price1.run_type = "actual"
    mock_price1.price = 48.50  # future period → forecast[0]

    mock_schedule = MagicMock()
    mock_schedule.prices = [mock_price0, mock_price1]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "prices": mock_schedule,
                "config": dict(subentry.data),
            }
        }

        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="c/kWh")
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

        attrs = entity.extra_state_attributes
        forecast = attrs["forecast"]
        assert len(forecast) == 1  # only the future period
        assert forecast[0]["price"] == pytest.approx(
            48.50 * NZD_PER_MWH_TO_C_PER_KWH, abs=0.001
        )


# ---------------------------------------------------------------------------
# T056 - forecast attribute shape (forecast_solar convention) - RED before T058
# ---------------------------------------------------------------------------


async def test_forecast_attribute_has_period_start_and_price_keys(
    hass, mock_entry
) -> None:
    """
    Forecast attribute uses period_start/price shape (not prices_array) (T056).

    This test is RED before T058: sensor.py still writes prices_array.
    After T058 it goes GREEN.
    """
    subentry = create_mock_subentry()
    mock_price1 = MagicMock()
    mock_price1.trading_datetime = datetime(2026, 5, 9, 17, 30, tzinfo=UTC)
    mock_price1.trading_period = 35
    mock_price1.node = "HAY2201"
    mock_price1.schedule = "RTD"
    mock_price1.run_type = "actual"
    mock_price1.price = 45.23

    mock_price2 = MagicMock()
    mock_price2.trading_datetime = datetime(2026, 5, 9, 18, 0, tzinfo=UTC)
    mock_price2.trading_period = 36
    mock_price2.node = "HAY2201"
    mock_price2.schedule = "RTD"
    mock_price2.run_type = "actual"
    mock_price2.price = 47.11

    mock_schedule = MagicMock()
    mock_schedule.prices = [mock_price1, mock_price2]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "prices": mock_schedule,
                "config": dict(subentry.data),
            }
        }

        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

        attrs = entity.extra_state_attributes

        # Must have forecast, not prices_array
        assert "forecast" in attrs, "forecast key missing from extra_state_attributes"
        assert "prices_array" not in attrs, "prices_array should not be present"

        forecast = attrs["forecast"]
        assert len(forecast) == 1  # only the future period (price2); price1 is state

        for item in forecast:
            assert "period_start" in item, f"period_start missing from: {item}"
            assert "price" in item, f"price missing from: {item}"
            # period_start must be ISO 8601 with timezone indicator
            ps = item["period_start"]
            assert isinstance(ps, str)
            assert "T" in ps, f"period_start not ISO8601: {ps}"
            assert "+" in ps or ps.endswith("Z"), f"period_start has no timezone: {ps}"

        # price1 (45.23) is the current period → state, not in forecast
        assert forecast[0]["price"] == pytest.approx(47.11, abs=0.001)


# ---------------------------------------------------------------------------
# T068 - forecast excludes current period (RED before T069)
# ---------------------------------------------------------------------------


async def test_forecast_starts_after_current_period(hass, mock_entry) -> None:
    """
    Forecast must NOT include the current period — only future periods (T068).

    This test is RED before T069: the current implementation includes all
    sorted_prices (including index 0) in the forecast.
    After T069 (slice to sorted_prices[1:]) it goes GREEN.
    """
    subentry = create_mock_subentry()
    t0 = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)  # current period → state
    t1 = datetime(2026, 5, 9, 12, 30, tzinfo=UTC)  # future period 1 → forecast[0]
    t2 = datetime(2026, 5, 9, 13, 0, tzinfo=UTC)  # future period 2 → forecast[1]

    def _make_price(dt, period, price) -> MagicMock:
        p = MagicMock()
        p.trading_datetime = dt
        p.trading_period = period
        p.node = "HAY2201"
        p.schedule = "RTD"
        p.run_type = "actual"
        p.price = price
        return p

    mock_schedule = MagicMock()
    mock_schedule.prices = [
        _make_price(t0, 24, 45.23),
        _make_price(t1, 25, 47.11),
        _make_price(t2, 26, 48.50),
    ]

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "prices": mock_schedule,
                "config": dict(subentry.data),
            }
        }

        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

    # State = current period
    assert entity.native_value == pytest.approx(45.23, abs=0.001)

    attrs = entity.extra_state_attributes
    forecast = attrs["forecast"]

    # Forecast must NOT include the current period (t0)
    current_ts = t0.isoformat()
    forecast_starts = [item["period_start"] for item in forecast]
    assert current_ts not in forecast_starts, (
        f"Current period {current_ts} should not be in forecast: {forecast_starts}"
    )

    # Forecast has exactly the future periods
    assert len(forecast) == 2
    assert forecast[0]["period_start"] == t1.isoformat()
    assert forecast[0]["price"] == pytest.approx(47.11, abs=0.001)
    assert forecast[1]["period_start"] == t2.isoformat()
    assert forecast[1]["price"] == pytest.approx(48.50, abs=0.001)


# ---------------------------------------------------------------------------
# T064 / T065 / T067 - Staleness guard for restored state
# ---------------------------------------------------------------------------


async def test_stale_restored_state_is_discarded(hass, mock_entry) -> None:
    """
    Entity discards restored state when timestamp is >30 min old (T064).

    This test is RED before T066: no staleness check exists yet.
    After T066 it goes GREEN.
    """
    subentry = create_mock_subentry()
    stale_ts = datetime(2026, 5, 9, 11, 0, tzinfo=UTC)  # 35 min before fake_now

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")

        mock_state = MagicMock()
        mock_state.state = "45.23"
        mock_state.attributes = {"timestamp": stale_ts.isoformat()}

        fake_now = datetime(2026, 5, 9, 11, 35, tzinfo=UTC)  # 35 min after stale_ts

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch("homeassistant.util.dt.utcnow", return_value=fake_now),
        ):
            await entity.async_added_to_hass()

    # Stale state must be discarded — entity is unavailable until coordinator fetches
    assert entity._native_value is None


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


async def test_fresh_restored_state_is_kept(hass, mock_entry) -> None:
    """
    Entity restores state when timestamp is ≤30 min old (T065).

    Even with coordinator.data=None the entity should be available and show
    the restored price.
    """
    subentry = create_mock_subentry()
    fresh_ts = datetime(2026, 5, 9, 11, 10, tzinfo=UTC)  # 25 min before fake_now

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")

        mock_state = MagicMock()
        mock_state.state = "45.23"
        mock_state.attributes = {"timestamp": fresh_ts.isoformat()}

        fake_now = datetime(2026, 5, 9, 11, 35, tzinfo=UTC)  # 25 min after fresh_ts

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch("homeassistant.util.dt.utcnow", return_value=fake_now),
        ):
            await entity.async_added_to_hass()

    assert entity._native_value == pytest.approx(45.23, abs=0.001)
    assert entity.available  # coordinator.data=None but restored value present


async def test_restore_boundary_exactly_30_minutes_is_available(
    hass, mock_entry
) -> None:
    """Timestamp exactly 30 min old is still fresh — entity restores (T067)."""
    subentry = create_mock_subentry()
    boundary_ts = datetime(2026, 5, 9, 11, 5, tzinfo=UTC)

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")

        mock_state = MagicMock()
        mock_state.state = "45.23"
        mock_state.attributes = {"timestamp": boundary_ts.isoformat()}

        fake_now = boundary_ts + timedelta(minutes=30)

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch("homeassistant.util.dt.utcnow", return_value=fake_now),
        ):
            await entity.async_added_to_hass()

    # Exactly 30 min → should restore (boundary is fresh/inclusive)
    assert entity._native_value == pytest.approx(45.23, abs=0.001)
    assert entity.available


async def test_restore_boundary_30_minutes_1_second_is_discarded(
    hass, mock_entry
) -> None:
    """Timestamp 30 min + 1 sec old is stale — entity discards restored state (T067)."""
    subentry = create_mock_subentry()
    boundary_ts = datetime(2026, 5, 9, 11, 5, tzinfo=UTC)

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        coordinator.data = None
        coordinator.last_update_success = True
        coordinator.async_request_refresh = AsyncMock()
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")

        mock_state = MagicMock()
        mock_state.state = "45.23"
        mock_state.attributes = {"timestamp": boundary_ts.isoformat()}

        fake_now = boundary_ts + timedelta(minutes=30, seconds=1)

        with (
            patch.object(CoordinatorEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                entity, "async_get_last_state", AsyncMock(return_value=mock_state)
            ),
            patch("homeassistant.util.dt.utcnow", return_value=fake_now),
        ):
            await entity.async_added_to_hass()

    # 30 min + 1 sec → stale, must discard
    assert entity._native_value is None
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
    assert [p["trading_period"] for p in attrs["forecast"]] == [24, 25, 26]
    assert [p["trading_period"] for p in attrs["history"]] == [23]


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
    assert [p["trading_period"] for p in attrs["forecast"]] == [24, 25]
    assert [p["trading_period"] for p in attrs["history"]] == [23]


async def test_intraday_current_period_not_duplicated_in_history(
    hass, mock_entry
) -> None:
    """Current intraday trade period should be state/forecast only, not history."""
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
    assert [p["trading_period"] for p in attrs["forecast"]] == [24, 25]
    assert [p["trading_period"] for p in attrs["history"]] == [23]


async def test_forecast_sensor_with_no_future_periods_stays_available(
    hass, mock_entry
) -> None:
    """Forecast sensors should not show unavailable when schedule data exists."""
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

    assert entity.available
    assert entity.native_value is None
