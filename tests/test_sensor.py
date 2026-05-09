"""Test sensor module for electricityinfo_nz integration."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import (
    DOMAIN,
    NZD_PER_MWH_TO_C_PER_KWH,
)
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator
from custom_components.electricityinfo.sensor import PriceSensorEntity
from tests.helpers import create_mock_subentry


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
    """Test setting up the integration creates a price sensor entity."""
    subentry = create_mock_subentry(
        subentry_id="test_hay_rtd",
        title="HAY2201 RTD (E)",
        schedule_type="RTD",
        market_type="E",
        node="HAY2201",
        forward_prices_count=24,
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
                "subentry_type": "sensor",
                "title": subentry.title,
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) >= 2  # 2 entities per subentry (NZD/MWh + c/kWh)

    price_sensors = [s for s in states if "hay2201" in s.entity_id]
    sensor_ids = [s.entity_id for s in states]
    assert len(price_sensors) > 0, f"No price sensors found. States: {sensor_ids}"


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
        assert len(forecast) == 2

        for item in forecast:
            assert "period_start" in item
            assert "price" in item
            assert isinstance(item["period_start"], str)
            assert "T" in item["period_start"]
            assert isinstance(item["price"], float)

        assert forecast[0]["price"] == pytest.approx(45.23, abs=0.001)
        assert forecast[1]["price"] == pytest.approx(47.11, abs=0.001)


async def test_ckwh_forecast_converts_price_field(hass, mock_entry) -> None:
    """c/kWh entity forecast prices are NZD/MWh x 0.1 (T054, updated by T061)."""
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

        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="c/kWh")
        with patch.object(entity, "async_write_ha_state", MagicMock()):
            entity._handle_coordinator_update()

        attrs = entity.extra_state_attributes
        forecast = attrs["forecast"]
        assert forecast[0]["price"] == pytest.approx(
            45.23 * NZD_PER_MWH_TO_C_PER_KWH, abs=0.001
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
        assert len(forecast) == 2

        for item in forecast:
            assert "period_start" in item, f"period_start missing from: {item}"
            assert "price" in item, f"price missing from: {item}"
            # period_start must be ISO 8601 with timezone indicator
            ps = item["period_start"]
            assert isinstance(ps, str)
            assert "T" in ps, f"period_start not ISO8601: {ps}"
            assert "+" in ps or ps.endswith("Z"), f"period_start has no timezone: {ps}"

        assert forecast[0]["price"] == pytest.approx(45.23, abs=0.001)
        assert forecast[1]["price"] == pytest.approx(47.11, abs=0.001)
