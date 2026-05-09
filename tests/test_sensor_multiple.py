"""Tests for multiple price sensors configuration and operation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from electricityinfo_nz.exceptions import MarketPricesAPIError
from homeassistant.config_entries import ConfigEntry

from custom_components.electricityinfo import ElectricityInfoCoordinator
from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_NODE,
    DOMAIN,
)
from custom_components.electricityinfo.sensor import PriceSensorEntity
from tests.helpers import create_mock_subentry


@pytest.fixture
def mock_config_entry_with_sensors():
    """Create mock config entry with two sensor subentries."""
    sub1 = create_mock_subentry(
        subentry_id="sensor_1",
        title="HAY2201 RTD (E)",
        schedule_type="RTD",
        market_type="E",
        node="HAY2201",
        forward_prices_count=24,
    )
    sub2 = create_mock_subentry(
        subentry_id="sensor_2",
        title="BEN2201 RTD (E)",
        schedule_type="RTD",
        market_type="E",
        node="BEN2201",
        forward_prices_count=24,
    )

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Electricity Info NZ"
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.subentries = {
        sub1.subentry_id: sub1,
        sub2.subentry_id: sub2,
    }
    return entry


@pytest.mark.asyncio
async def test_multiple_sensors_configuration_storage(mock_config_entry_with_sensors):
    """Test that multiple sensor subentries are stored and retrievable (T033)."""
    entry = mock_config_entry_with_sensors
    subentries = [s for s in entry.subentries.values() if s.subentry_type == "sensor"]

    assert len(subentries) == 2
    assert subentries[0].subentry_id == "sensor_1"
    assert subentries[0].data[CONF_NODE] == "HAY2201"

    assert subentries[1].subentry_id == "sensor_2"
    assert subentries[1].data[CONF_NODE] == "BEN2201"


@pytest.mark.asyncio
async def test_multiple_sensors_create_unique_entities(
    hass, mock_config_entry_with_sensors
):
    """Test that multiple subentries create separate entities (T033)."""
    entry = mock_config_entry_with_sensors

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)

        entities = [
            PriceSensorEntity(coordinator, entry, subentry, unit="NZD/MWh")
            for subentry in entry.subentries.values()
        ]

        assert len(entities) == 2

        unique_ids = [e._attr_unique_id for e in entities]
        assert len(unique_ids) == len(set(unique_ids))


@pytest.mark.asyncio
async def test_multiple_sensors_data_isolation(hass, mock_config_entry_with_sensors):
    """Test that coordinator provides isolated data per sensor (T035)."""
    entry = mock_config_entry_with_sensors

    with patch(
        "custom_components.electricityinfo.AsyncMarketPricesClient"
    ) as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        mock_client_instance.get_schedule_prices.return_value = MagicMock()

        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.client = mock_client_instance

        result = await coordinator._async_update_data()

        assert "sensor_1" in result
        assert "sensor_2" in result
        mock_client_instance.get_schedule_prices.assert_called()


@pytest.mark.asyncio
async def test_isolated_failure_partial_data(hass, mock_config_entry_with_sensors):
    """Test isolated failure: one sensor fails, others update normally (T036)."""
    entry = mock_config_entry_with_sensors

    with patch(
        "custom_components.electricityinfo.AsyncMarketPricesClient"
    ) as mock_client_class:
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        # First subentry succeeds, second raises a per-sensor API error
        mock_client_instance.get_schedule_prices.side_effect = [
            MagicMock(),
            MarketPricesAPIError("API Error for sensor 2"),
        ]

        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.client = mock_client_instance

        result = await coordinator._async_update_data()

        assert "sensor_1" in result
        assert "sensor_2" in result
        assert "error" not in result["sensor_1"]
        assert "error" in result["sensor_2"]


@pytest.mark.asyncio
async def test_unique_unique_id_per_sensor(hass, mock_config_entry_with_sensors):
    """Test unique_id uniqueness per sensor subentry (T037)."""
    entry = mock_config_entry_with_sensors

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)

        unique_ids = [
            PriceSensorEntity(
                coordinator, entry, subentry, unit="NZD/MWh"
            )._attr_unique_id
            for subentry in entry.subentries.values()
        ]

        assert len(unique_ids) == len(set(unique_ids)), "Unique IDs are not unique"
        assert len(unique_ids) == 2

        for uid in unique_ids:
            assert "electricityinfo_nz" in uid


@pytest.mark.asyncio
async def test_multiple_sensors_in_config_flow(hass, mock_config_entry_with_sensors):
    """Test subentries support multiple sensors with individual management (T034)."""
    entry = mock_config_entry_with_sensors
    subentries = list(entry.subentries.values())

    assert len(subentries) == 2

    # Each subentry has its own node
    nodes = {s.data[CONF_NODE] for s in subentries}
    assert "HAY2201" in nodes
    assert "BEN2201" in nodes

    # Each subentry has a unique ID
    ids = {s.subentry_id for s in subentries}
    assert len(ids) == 2
