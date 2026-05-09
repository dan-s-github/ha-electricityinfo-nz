"""Tests for price unit conversion (NZD/MWh <-> c/kWh)."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.electricityinfo import ElectricityInfoCoordinator
from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    NZD_PER_MWH_TO_C_PER_KWH,
)
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
# T055 - c/kWh prices_array price field conversion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ckwh_entity_prices_array_converts_price_field(hass, mock_entry):
    """c/kWh prices_array multiplies NZD/MWh prices by conversion factor (T055)."""
    subentry = create_mock_subentry()
    nzd_price = 452.3  # NZD/MWh

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, mock_entry)
        entity = PriceSensorEntity(coordinator, mock_entry, subentry, unit="c/kWh")

    # Set attributes directly — _attributes always stores prices in NZD/MWh
    entity._attributes = {
        "prices_array": [
            {
                "trading_date": "2026-05-09",
                "trading_period": 35,
                "price": nzd_price,  # canonical NZD/MWh value
            }
        ]
    }
    entity._native_value = nzd_price

    attrs = entity.extra_state_attributes
    prices = attrs["prices_array"]
    assert len(prices) == 1
    assert prices[0]["price"] == pytest.approx(
        nzd_price * NZD_PER_MWH_TO_C_PER_KWH, rel=1e-4
    )
    assert prices[0]["trading_date"] == "2026-05-09"
    assert prices[0]["trading_period"] == 35
