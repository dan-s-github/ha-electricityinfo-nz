"""Tests for price unit conversion (NZD/MWh <-> c/kWh)."""

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_FORWARD_PRICES_COUNT,
    CONF_MARKET_TYPE,
    CONF_NODE,
    CONF_SCHEDULE_TYPE,
    CONF_SENSOR_ID,
    CONF_SENSORS,
    CONF_UNIT_PREFERENCE,
    DOMAIN,
    NZD_PER_MWH_TO_C_PER_KWH,
)
from custom_components.electricityinfo.sensor import PriceSensorEntity


@pytest.fixture
def mock_entry_with_sensor_nzd():
    """Create mock config entry with sensor in NZD/MWh."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.options = {
        CONF_SENSORS: [
            {
                CONF_SENSOR_ID: "price_sensor_nzd",
                CONF_SCHEDULE_TYPE: "daily_spot",
                CONF_MARKET_TYPE: "ENERGY",
                CONF_NODE: "NEA",
                CONF_FORWARD_PRICES_COUNT: 24,
                CONF_UNIT_PREFERENCE: "NZD/MWh",
            }
        ]
    }
    return entry


@pytest.fixture
def mock_entry_with_sensor_c_per_kwh():
    """Create mock config entry with sensor in c/kWh."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.options = {
        CONF_SENSORS: [
            {
                CONF_SENSOR_ID: "price_sensor_c_per_kwh",
                CONF_SCHEDULE_TYPE: "daily_spot",
                CONF_MARKET_TYPE: "ENERGY",
                CONF_NODE: "NEA",
                CONF_FORWARD_PRICES_COUNT: 24,
                CONF_UNIT_PREFERENCE: "c/kWh",
            }
        ]
    }
    return entry


@pytest.mark.asyncio
async def test_unit_conversion_constant(hass):
    """Test that unit conversion constant is correct (T038)."""
    # 1 NZD/MWh = 0.1 c/kWh
    assert NZD_PER_MWH_TO_C_PER_KWH == 0.1


@pytest.mark.asyncio
async def test_sensor_unit_of_measurement_nzd(hass, mock_entry_with_sensor_nzd):
    """Test that sensor displays correct unit for NZD/MWh (T039)."""
    from custom_components.electricityinfo import ElectricityInfoCoordinator

    entry = mock_entry_with_sensor_nzd

    with patch("custom_components.electricityinfo.MarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)
        sensor_config = entry.options[CONF_SENSORS][0]

        entity = PriceSensorEntity(coordinator, entry, sensor_config)

        # Verify unit of measurement
        assert entity.native_unit_of_measurement == "NZD/MWh"


@pytest.mark.asyncio
async def test_sensor_unit_of_measurement_c_per_kwh(
    hass, mock_entry_with_sensor_c_per_kwh
):
    """Test that sensor displays correct unit for c/kWh (T039)."""
    from custom_components.electricityinfo import ElectricityInfoCoordinator

    entry = mock_entry_with_sensor_c_per_kwh

    with patch("custom_components.electricityinfo.MarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)
        sensor_config = entry.options[CONF_SENSORS][0]

        entity = PriceSensorEntity(coordinator, entry, sensor_config)

        # Verify unit of measurement
        assert entity.native_unit_of_measurement == "c/kWh"


@pytest.mark.asyncio
async def test_unit_conversion_nzd_to_c_per_kwh(hass):
    """Test NZD/MWh to c/kWh conversion accuracy (T040)."""
    test_cases = [
        (100, 10.0),  # 100 NZD/MWh = 10 c/kWh
        (200, 20.0),  # 200 NZD/MWh = 20 c/kWh
        (50, 5.0),  # 50 NZD/MWh = 5 c/kWh
        (150.5, 15.05),  # 150.5 NZD/MWh = 15.05 c/kWh
    ]

    for nzd_price, expected_c_per_kwh in test_cases:
        converted = nzd_price * NZD_PER_MWH_TO_C_PER_KWH
        # Check accuracy within ±0.01 c/kWh
        assert abs(converted - expected_c_per_kwh) < 0.01


@pytest.mark.asyncio
async def test_unit_conversion_c_per_kwh_to_nzd(hass):
    """Test c/kWh to NZD/MWh conversion accuracy (T040)."""
    test_cases = [
        (10.0, 100),  # 10 c/kWh = 100 NZD/MWh
        (20.0, 200),  # 20 c/kWh = 200 NZD/MWh
        (5.0, 50),  # 5 c/kWh = 50 NZD/MWh
        (15.05, 150.5),  # 15.05 c/kWh = 150.5 NZD/MWh
    ]

    for c_per_kwh, expected_nzd in test_cases:
        converted = c_per_kwh / NZD_PER_MWH_TO_C_PER_KWH
        # Check accuracy within ±0.01 NZD/MWh
        assert abs(converted - expected_nzd) < 0.01


@pytest.mark.asyncio
async def test_dynamic_unit_reconfiguration_simulation(
    hass, mock_entry_with_sensor_nzd
):
    """Test simulation of dynamic unit reconfiguration (T041)."""
    from custom_components.electricityinfo import ElectricityInfoCoordinator

    entry = mock_entry_with_sensor_nzd

    with patch("custom_components.electricityinfo.MarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)

        # Create entity with NZD/MWh
        sensor_config_nzd = entry.options[CONF_SENSORS][0]
        entity_nzd = PriceSensorEntity(coordinator, entry, sensor_config_nzd)

        assert entity_nzd.native_unit_of_measurement == "NZD/MWh"

        # Simulate changing unit to c/kWh by creating new config
        sensor_config_c_per_kwh = {
            CONF_SENSOR_ID: "price_sensor_c_per_kwh",
            CONF_SCHEDULE_TYPE: "daily_spot",
            CONF_MARKET_TYPE: "ENERGY",
            CONF_NODE: "NEA",
            CONF_FORWARD_PRICES_COUNT: 24,
            CONF_UNIT_PREFERENCE: "c/kWh",
        }

        entity_c_per_kwh = PriceSensorEntity(
            coordinator, entry, sensor_config_c_per_kwh
        )

        # Verify new unit is applied
        assert entity_c_per_kwh.native_unit_of_measurement == "c/kWh"


@pytest.mark.asyncio
async def test_unit_conversion_rounding(hass):
    """Test that unit conversion handles rounding correctly (T040)."""
    # Test values that might have rounding issues
    test_cases = [
        (100.123, 10.0123),  # Multiple decimals
        (99.999, 9.9999),  # Near-round values
        (0.001, 0.0001),  # Very small values
        (999.999, 99.9999),  # Large values
    ]

    for nzd_price, expected_c_per_kwh in test_cases:
        converted = nzd_price * NZD_PER_MWH_TO_C_PER_KWH
        # Check accuracy within ±0.01 c/kWh
        assert abs(converted - expected_c_per_kwh) < 0.01
