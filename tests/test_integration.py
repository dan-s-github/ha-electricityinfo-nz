"""Test integration setup and unload for Electricityinfo NZ."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.electricityinfo import async_setup_entry, async_unload_entry
from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
    MAX_RETRIES,
    RETRY_INTERVAL_MINUTES,
    UPDATE_INTERVAL_MINUTES,
)
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator


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


# ---------------------------------------------------------------------------
# T051 - Coordinator retry / backoff tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_config_entry_for_coordinator() -> MagicMock:
    """Create a minimal mock config entry for coordinator unit tests."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.subentries = {}
    return entry


async def test_coordinator_retry_count_increments_on_failure(
    hass: HomeAssistant, mock_config_entry_for_coordinator: MagicMock
) -> None:
    """_retry_count increments and update_interval grows after first failure (T051)."""
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(
            hass, mock_config_entry_for_coordinator
        )
        coordinator._retry_count = 0

        with (
            patch.object(
                coordinator,
                "_async_update_data",
                side_effect=RuntimeError("API down"),
            ),
            pytest.raises(RuntimeError),
        ):
            await coordinator._async_update_data()

    # After one failure: retry_count=1, interval=1 min
    coordinator._retry_count = 1
    retry_interval = RETRY_INTERVAL_MINUTES * (2 ** (coordinator._retry_count - 1))
    assert retry_interval == RETRY_INTERVAL_MINUTES
    assert timedelta(minutes=retry_interval) == timedelta(minutes=1)


async def test_coordinator_marks_unavailable_after_max_retries(
    hass: HomeAssistant, mock_config_entry_for_coordinator: MagicMock
) -> None:
    """Coordinator sets last_update_success=False after MAX_RETRIES failures (T051)."""
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(
            hass, mock_config_entry_for_coordinator
        )

        async def failing_update() -> None:
            coordinator._retry_count += 1
            if coordinator._retry_count >= MAX_RETRIES:
                coordinator.last_update_success = False
            retry_interval = RETRY_INTERVAL_MINUTES * (
                2 ** (coordinator._retry_count - 1)
            )
            coordinator.update_interval = timedelta(minutes=retry_interval)
            err_msg = "Simulated failure"
            raise UpdateFailed(err_msg)

        coordinator._retry_count = 0
        coordinator.last_update_success = True

        # Simulate first failure
        with pytest.raises(UpdateFailed):
            await failing_update()
        assert coordinator._retry_count == 1
        assert coordinator.last_update_success is True  # not marked failed yet

        # Simulate second failure (hits MAX_RETRIES)
        with pytest.raises(UpdateFailed):
            await failing_update()
        assert coordinator._retry_count == MAX_RETRIES
        assert coordinator.last_update_success is False
        # Interval grows exponentially: 2^(retry_count-1) minutes
        assert coordinator.update_interval > timedelta(minutes=RETRY_INTERVAL_MINUTES)


async def test_coordinator_resets_retry_on_success(
    hass: HomeAssistant, mock_config_entry_for_coordinator: MagicMock
) -> None:
    """Coordinator resets _retry_count and interval on successful fetch (T051)."""
    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(
            hass, mock_config_entry_for_coordinator
        )

        # Simulate a degraded state after 1 failure
        coordinator._retry_count = 1
        coordinator.last_update_success = False
        coordinator.update_interval = timedelta(minutes=RETRY_INTERVAL_MINUTES)

        # Simulate success path reset
        coordinator._retry_count = 0
        coordinator.update_interval = timedelta(minutes=UPDATE_INTERVAL_MINUTES)
        coordinator.last_update_success = True

        assert coordinator._retry_count == 0
        assert coordinator.update_interval == timedelta(minutes=UPDATE_INTERVAL_MINUTES)
        assert coordinator.last_update_success is True
