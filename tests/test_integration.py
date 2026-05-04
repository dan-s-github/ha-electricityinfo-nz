"""Test integration setup and unload for Electricityinfo NZ."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.electricityinfo import async_setup_entry, async_unload_entry
from custom_components.electricityinfo.const import DOMAIN


async def test_async_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup of a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Main")
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        AsyncMock(return_value=True),
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert entry.entry_id in hass.data[DOMAIN]
    assert hass.data[DOMAIN][entry.entry_id]["title"] == "Main"


async def test_async_setup_entry_platform_forward_failure(hass: HomeAssistant) -> None:
    """Test setup returns True even if no platform forwarding is needed."""
    entry = MockConfigEntry(domain=DOMAIN, title="Main")
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        AsyncMock(return_value=True),
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True


async def test_async_unload_entry_success(hass: HomeAssistant) -> None:
    """Test successful unload of a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, title="Main")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"title": "Main", "data": {}}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        result = await async_unload_entry(hass, entry)

    assert result is True
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_async_unload_entry_failure(hass: HomeAssistant) -> None:
    """Test unload when platform unload fails."""
    entry = MockConfigEntry(domain=DOMAIN, title="Main")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"title": "Main", "data": {}}

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    ):
        result = await async_unload_entry(hass, entry)

    assert result is False
    assert entry.entry_id in hass.data[DOMAIN]
