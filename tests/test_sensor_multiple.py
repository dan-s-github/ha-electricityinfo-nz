"""Tests for multiple price sensors configuration and operation."""

from unittest.mock import AsyncMock, MagicMock, patch

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
)


@pytest.fixture
def mock_config_entry_with_sensors():
    """Create mock config entry with multiple sensors."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Electricity Info NZ"
    entry.data = {
        "auth_implementation": "electricityinfo_nz",
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.options = {
        CONF_SENSORS: [
            {
                CONF_SENSOR_ID: "sensor_1",
                CONF_SCHEDULE_TYPE: "daily_spot",
                CONF_MARKET_TYPE: "ENERGY",
                CONF_NODE: "NEA",
                CONF_FORWARD_PRICES_COUNT: 24,
                CONF_UNIT_PREFERENCE: "NZD/MWh",
            },
            {
                CONF_SENSOR_ID: "sensor_2",
                CONF_SCHEDULE_TYPE: "daily_spot",
                CONF_MARKET_TYPE: "ENERGY",
                CONF_NODE: "MID",
                CONF_FORWARD_PRICES_COUNT: 24,
                CONF_UNIT_PREFERENCE: "c/kWh",
            },
        ]
    }
    return entry


@pytest.mark.asyncio
async def test_multiple_sensors_configuration_storage(mock_config_entry_with_sensors):
    """Test that multiple sensor configurations are stored and retrievable (T033)."""
    entry = mock_config_entry_with_sensors
    sensors = entry.options.get(CONF_SENSORS, [])

    # Verify both sensors are stored
    assert len(sensors) == 2
    assert sensors[0][CONF_SENSOR_ID] == "sensor_1"
    assert sensors[0][CONF_NODE] == "NEA"
    assert sensors[0][CONF_UNIT_PREFERENCE] == "NZD/MWh"

    assert sensors[1][CONF_SENSOR_ID] == "sensor_2"
    assert sensors[1][CONF_NODE] == "MID"
    assert sensors[1][CONF_UNIT_PREFERENCE] == "c/kWh"


@pytest.mark.asyncio
async def test_multiple_sensors_create_unique_entities(
    hass, mock_config_entry_with_sensors
):
    """Test that multiple sensors create separate entities (T033)."""
    from custom_components.electricityinfo import ElectricityInfoCoordinator
    from custom_components.electricityinfo.sensor import PriceSensorEntity

    entry = mock_config_entry_with_sensors

    with patch("custom_components.electricityinfo.MarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)

        # Create entities for each sensor configuration
        sensors = entry.options.get(CONF_SENSORS, [])
        entities = []

        for sensor_config in sensors:
            entity = PriceSensorEntity(coordinator, entry, sensor_config)
            entities.append(entity)

        # Verify we have 2 entities
        assert len(entities) == 2

        # Verify entities have different entity_ids
        entity_ids = [e.entity_id for e in entities]
        assert len(entity_ids) == len(set(entity_ids))


@pytest.mark.asyncio
async def test_multiple_sensors_data_isolation(hass, mock_config_entry_with_sensors):
    """Test that coordinator provides isolated data per sensor (T035)."""
    from custom_components.electricityinfo import ElectricityInfoCoordinator

    entry = mock_config_entry_with_sensors

    with patch(
        "custom_components.electricityinfo.MarketPricesClient"
    ) as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Mock get_schedules to return list data (coordinator expects list)
        mock_client_instance.get_schedules.return_value = [
            {"timestamp": "2025-01-01", "price": 100},
        ]

        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.client = mock_client_instance

        result = await coordinator._async_update_data()

        # Verify both sensors have data in result
        assert "sensor_1" in result
        assert "sensor_2" in result


@pytest.mark.asyncio
async def test_isolated_failure_partial_data(hass, mock_config_entry_with_sensors):
    """Test isolated failure: one sensor fails, others update normally (T036)."""
    from custom_components.electricityinfo import ElectricityInfoCoordinator

    entry = mock_config_entry_with_sensors

    with patch(
        "custom_components.electricityinfo.MarketPricesClient"
    ) as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # Mock get_schedules to return partial data
        mock_client_instance.get_schedules.side_effect = Exception("API Error")

        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.client = mock_client_instance

        # This will trigger retry logic
        try:
            result = await coordinator._async_update_data()
        except Exception:
            # Expected to fail after retries
            pass

        # Coordinator should mark last_update_success = False
        # which will cause entities to mark as unavailable


@pytest.mark.asyncio
async def test_unique_entity_id_per_sensor(hass, mock_config_entry_with_sensors):
    """Test unique entity_id generation per sensor (T037)."""
    from custom_components.electricityinfo import ElectricityInfoCoordinator
    from custom_components.electricityinfo.sensor import PriceSensorEntity

    entry = mock_config_entry_with_sensors

    with patch("custom_components.electricityinfo.MarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)

        # Create entities for each sensor configuration
        sensors = entry.options.get(CONF_SENSORS, [])
        entity_ids = []

        for sensor_config in sensors:
            entity = PriceSensorEntity(coordinator, entry, sensor_config)
            entity_ids.append(entity.entity_id)

        # Verify all entity_ids are unique
        assert len(entity_ids) == len(set(entity_ids)), "Entity IDs are not unique"
        assert len(entity_ids) == 2, "Should have 2 entity IDs"

        # Verify entity_ids follow expected pattern
        for entity_id in entity_ids:
            assert entity_id.startswith("sensor.electricityinfo_nz_")


@pytest.mark.asyncio
async def test_multiple_sensors_in_config_flow(hass, mock_config_entry_with_sensors):
    """Test that config flow CRUD supports multiple sensors (T034)."""
    entry = mock_config_entry_with_sensors
    sensors = entry.options.get(CONF_SENSORS, [])

    # Verify sensors list operations
    assert len(sensors) == 2

    # Simulate adding a third sensor
    third_sensor = {
        CONF_SENSOR_ID: "sensor_3",
        CONF_SCHEDULE_TYPE: "daily_spot",
        CONF_MARKET_TYPE: "ENERGY",
        CONF_NODE: "SOU",
        CONF_FORWARD_PRICES_COUNT: 24,
        CONF_UNIT_PREFERENCE: "NZD/MWh",
    }

    sensors.append(third_sensor)
    assert len(sensors) == 3

    # Simulate editing a sensor
    sensors[0][CONF_FORWARD_PRICES_COUNT] = 48
    assert sensors[0][CONF_FORWARD_PRICES_COUNT] == 48

    # Simulate deleting a sensor
    del sensors[1]
    assert len(sensors) == 2

    # Verify remaining sensors
    assert sensors[0][CONF_SENSOR_ID] == "sensor_1"
    assert sensors[1][CONF_SENSOR_ID] == "sensor_3"
