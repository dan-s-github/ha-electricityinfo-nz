"""Test sensor module for electricityinfo_nz integration."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo_nz.const import DOMAIN


async def test_sensor_platform_sets_up(hass) -> None:
    """Test setting up the integration creates one scaffold sensor."""
    entry = MockConfigEntry(domain=DOMAIN, title="Main")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) == 1
    assert states[0].state == "1"
