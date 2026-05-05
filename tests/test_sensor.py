"""Test sensor module for electricityinfo_nz integration."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import (
    CONF_SENSORS,
    DOMAIN,
)
from tests.helpers import create_mock_sensor_config


async def test_sensor_platform_sets_up(hass) -> None:
    """Test setting up the integration creates a price sensor entity."""
    # Create sensor configuration
    sensor_config = create_mock_sensor_config(
        sensor_id="test_nea_daily",
        schedule_type="daily_spot",
        market_type="energy",
        node="NEA",
        forward_prices_count=24,
        unit_preference="NZD/MWh",
    )

    # Create config entry with sensors configured
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main",
        data={
            "client_id": "test_client",
            "client_secret": "test_secret",
        },
        options={
            CONF_SENSORS: [sensor_config],
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify sensor entity is created
    states = hass.states.async_all("sensor")
    assert len(states) >= 1  # At least one sensor should be created

    # Find our price sensor
    price_sensors = [s for s in states if "electricityinfo_nz_nea" in s.entity_id]
    sensor_ids = [s.entity_id for s in states]
    assert len(price_sensors) > 0, f"No price sensors found. States: {sensor_ids}"
