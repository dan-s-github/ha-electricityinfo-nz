"""Test sensor module for electricityinfo_nz integration."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import DOMAIN
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator
from tests.helpers import create_mock_subentry


@pytest.fixture(autouse=True)
def mock_coordinator_update():
    """Prevent real API calls by stubbing out the coordinator data fetch."""
    with patch.object(
        ElectricityInfoCoordinator, "_async_update_data", return_value={}
    ):
        yield


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
