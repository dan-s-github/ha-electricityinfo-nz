"""Tests for price unit conversion (NZD/MWh <-> c/kWh)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    NZD_PER_MWH_TO_C_PER_KWH,
)
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator
from custom_components.electricityinfo.sensor import PriceSensorEntity
from tests.helpers import create_mock_subentry


@pytest.fixture
def mock_entry():
    """Create minimal mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.subentries = {}
    return entry


@pytest.mark.asyncio
async def test_unit_conversion_constant(hass):
    """Test that unit conversion constant is correct (T038)."""
    assert NZD_PER_MWH_TO_C_PER_KWH == 0.1


@pytest.mark.asyncio
async def test_sensor_unit_of_measurement_nzd(hass, mock_entry):
    """Test that sensor displays correct unit for NZD/MWh (T039)."""
    subentry = create_mock_subentry()

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="NZD/MWh")
        assert entity.native_unit_of_measurement == "NZD/MWh"


@pytest.mark.asyncio
async def test_sensor_unit_of_measurement_c_per_kwh(hass, mock_entry):
    """Test that sensor displays correct unit for c/kWh (T039)."""
    subentry = create_mock_subentry()

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="c/kWh")
        assert entity.native_unit_of_measurement == "c/kWh"


@pytest.mark.asyncio
async def test_unit_conversion_nzd_to_c_per_kwh(hass):
    """Test NZD/MWh to c/kWh conversion accuracy (T040)."""
    test_cases = [
        (100, 10.0),
        (200, 20.0),
        (50, 5.0),
        (150.5, 15.05),
    ]
    for nzd_price, expected_c_per_kwh in test_cases:
        converted = nzd_price * NZD_PER_MWH_TO_C_PER_KWH
        assert abs(converted - expected_c_per_kwh) < 0.01


@pytest.mark.asyncio
async def test_unit_conversion_c_per_kwh_to_nzd(hass):
    """Test c/kWh to NZD/MWh conversion accuracy (T040)."""
    test_cases = [
        (10.0, 100),
        (20.0, 200),
        (5.0, 50),
        (15.05, 150.5),
    ]
    for c_per_kwh, expected_nzd in test_cases:
        converted = c_per_kwh / NZD_PER_MWH_TO_C_PER_KWH
        assert abs(converted - expected_nzd) < 0.01


@pytest.mark.asyncio
async def test_dynamic_unit_reconfiguration_simulation(hass, mock_entry):
    """Test simulation of dynamic unit reconfiguration (T041)."""
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)

        entity_nzd = PriceSensorEntity(
            coordinator, mock_entry, create_mock_subentry(), unit="NZD/MWh"
        )
        assert entity_nzd.native_unit_of_measurement == "NZD/MWh"

        entity_c = PriceSensorEntity(
            coordinator, mock_entry, create_mock_subentry(), unit="c/kWh"
        )
        assert entity_c.native_unit_of_measurement == "c/kWh"


@pytest.mark.asyncio
async def test_unit_conversion_rounding(hass):
    """Test that unit conversion handles rounding correctly (T040)."""
    test_cases = [
        (100.123, 10.0123),
        (99.999, 9.9999),
        (0.001, 0.0001),
        (999.999, 99.9999),
    ]
    for nzd_price, expected_c_per_kwh in test_cases:
        converted = nzd_price * NZD_PER_MWH_TO_C_PER_KWH
        assert abs(converted - expected_c_per_kwh) < 0.01


# ---------------------------------------------------------------------------
# T055 / T062 - forecast attribute c/kWh conversion (updated from prices_array)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ckwh_entity_forecast_converts_price_field_direct(hass, mock_entry):
    """c/kWh forecast prices are multiplied by NZD_PER_MWH_TO_C_PER_KWH (T055/T062)."""
    subentry = create_mock_subentry()
    nzd_price = 452.3  # NZD/MWh

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="c/kWh")

    # Set attributes directly - _attributes always stores prices in NZD/MWh canonically
    entity._attributes = {
        "forecast": [
            {
                "period_start": "2026-05-09T17:30:00+00:00",
                "price": nzd_price,  # canonical NZD/MWh value
            }
        ]
    }
    entity._native_value = nzd_price

    attrs = entity.extra_state_attributes
    forecast = attrs["forecast"]
    assert len(forecast) == 1
    assert forecast[0]["price"] == pytest.approx(
        nzd_price * NZD_PER_MWH_TO_C_PER_KWH, rel=1e-4
    )
    assert forecast[0]["period_start"] == "2026-05-09T17:30:00+00:00"


# ---------------------------------------------------------------------------
# T057 - forecast attribute c/kWh conversion (forecast_solar convention)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ckwh_entity_forecast_converts_price_field(hass, mock_entry):
    """c/kWh forecast attribute prices are in c/kWh (not NZD/MWh) (T057, T070)."""
    subentry = create_mock_subentry()
    nzd_current = 452.3  # NZD/MWh — current period → state, not in forecast
    nzd_future = 480.0  # NZD/MWh — future period → forecast[0]

    mock_price0 = MagicMock()
    mock_price0.trading_datetime = datetime(2026, 5, 9, 17, 30, tzinfo=UTC)
    mock_price0.trading_period = 35
    mock_price0.node = "HAY2201"
    mock_price0.schedule = "RTD"
    mock_price0.run_type = "actual"
    mock_price0.price = nzd_current

    mock_price1 = MagicMock()
    mock_price1.trading_datetime = datetime(2026, 5, 9, 18, 0, tzinfo=UTC)
    mock_price1.trading_period = 36
    mock_price1.node = "HAY2201"
    mock_price1.schedule = "RTD"
    mock_price1.run_type = "actual"
    mock_price1.price = nzd_future

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

        # Must use forecast key, not prices_array
        err_msg = "forecast key missing from c/kWh extra_state_attributes"
        assert "forecast" in attrs, err_msg
        assert "prices_array" not in attrs

        forecast = attrs["forecast"]
        # Only the future period (nzd_future) appears in forecast; nzd_current is state
        assert len(forecast) == 1
        expected_c_per_kwh = nzd_future * NZD_PER_MWH_TO_C_PER_KWH
        assert forecast[0]["price"] == pytest.approx(expected_c_per_kwh, rel=1e-4)
        assert "period_start" in forecast[0]
