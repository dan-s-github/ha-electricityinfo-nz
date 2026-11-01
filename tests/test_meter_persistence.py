"""Tests for persisting meter readings across restarts and reloads."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.electricityinfo import async_remove_entry, async_unload_entry
from custom_components.electricityinfo.const import (
    DOMAIN,
    METER_READING_MAX_AGE_MINUTES,
)
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator
from custom_components.electricityinfo.sensor import (
    DailyImportCostSensor,
    ImportCostSensor,
    PreviousDayImportCostSensor,
)
from tests.helpers import create_mock_market_node_subentry

ENTRY_ID = "test_entry_id"
STORE_KEY = f"{DOMAIN}.{ENTRY_ID}.meter_readings"
SUBENTRY_ID = "market_node_1"
SUBENTRY_DATA = {
    "node": "HAY2201",
    "import_meter_entity_id": "sensor.import_energy",
    "export_meter_entity_id": "sensor.export_energy",
}


def _entry(subentry_data: dict | None = None) -> MagicMock:
    """Build a mock config entry with one market_node subentry."""
    entry = MagicMock()
    entry.entry_id = ENTRY_ID
    entry.subentries = {
        SUBENTRY_ID: SimpleNamespace(
            subentry_id=SUBENTRY_ID,
            subentry_type="market_node",
            data=subentry_data or SUBENTRY_DATA,
        )
    }
    return entry


def _seed_store(hass_storage: dict, reading: dict) -> None:
    """Seed stored meter readings as written before a restart."""
    hass_storage[STORE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {SUBENTRY_ID: reading},
    }


def _reading(age: timedelta, **overrides) -> dict:
    """Build a stored reading saved `age` ago."""
    return {
        "saved_at": (dt_util.utcnow() - age).isoformat(),
        "import_entity": "sensor.import_energy",
        "import": 10.0,
        "export_entity": "sensor.export_energy",
        "export": 5.0,
        **overrides,
    }


async def test_recent_reading_is_restored(hass, hass_storage) -> None:
    """A reading saved shortly before restart seeds the previous meter values."""
    _seed_store(hass_storage, _reading(timedelta(minutes=5)))
    coordinator = ElectricityInfoCoordinator(hass, _entry())

    await coordinator.async_load_meter_readings()

    assert coordinator._meter_prev_import[SUBENTRY_ID] == 10.0
    assert coordinator._meter_prev_export[SUBENTRY_ID] == 5.0


async def test_stale_reading_is_ignored(hass, hass_storage) -> None:
    """A reading older than the max age is not used."""
    age = timedelta(minutes=METER_READING_MAX_AGE_MINUTES + 1)
    _seed_store(hass_storage, _reading(age))
    coordinator = ElectricityInfoCoordinator(hass, _entry())

    await coordinator.async_load_meter_readings()

    assert SUBENTRY_ID not in coordinator._meter_prev_import
    assert SUBENTRY_ID not in coordinator._meter_prev_export


async def test_reading_from_a_different_meter_is_ignored(hass, hass_storage) -> None:
    """A reading taken from a meter that is no longer configured is not used."""
    _seed_store(
        hass_storage,
        _reading(timedelta(minutes=5), import_entity="sensor.old_import"),
    )
    coordinator = ElectricityInfoCoordinator(hass, _entry())

    await coordinator.async_load_meter_readings()

    assert SUBENTRY_ID not in coordinator._meter_prev_import
    assert coordinator._meter_prev_export[SUBENTRY_ID] == 5.0


async def test_readings_saved_and_restored_across_reload(hass, hass_storage) -> None:
    """Readings saved on each poll give the next coordinator its first delta."""
    first = ElectricityInfoCoordinator(hass, _entry())
    with patch.object(first, "_read_energy_meter", side_effect=[10.0, 5.0]):
        first._populate_accounting_metrics(
            SUBENTRY_ID, SUBENTRY_DATA, _settled_node_data()
        )
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass_storage[STORE_KEY]["data"][SUBENTRY_ID]["import"] == 10.0

    second = ElectricityInfoCoordinator(hass, _entry())
    await second.async_load_meter_readings()
    node_data = _settled_node_data()
    with patch.object(second, "_read_energy_meter", side_effect=[11.5, 5.4]):
        second._populate_accounting_metrics(SUBENTRY_ID, SUBENTRY_DATA, node_data)

    assert node_data["import_energy_delta"] == pytest.approx(1.5, abs=1e-9)
    assert node_data["export_energy_delta"] == pytest.approx(0.4, abs=1e-9)


async def test_unload_flushes_readings(hass) -> None:
    """Unloading the entry writes the latest readings before a reload."""
    entry = MockConfigEntry(domain=DOMAIN, title="Main")
    coordinator = MagicMock()
    coordinator.async_save_meter_readings = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"coordinator": coordinator}

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ):
        assert await async_unload_entry(hass, entry)

    coordinator.async_save_meter_readings.assert_awaited_once()


async def test_remove_entry_deletes_stored_readings(hass, hass_storage) -> None:
    """Deleting the config entry removes its stored readings."""
    _seed_store(hass_storage, _reading(timedelta(minutes=5)))
    entry = MockConfigEntry(domain=DOMAIN, title="Main", entry_id=ENTRY_ID)

    await async_remove_entry(hass, entry)

    assert STORE_KEY not in hass_storage


@pytest.mark.parametrize(("price_unit", "precision"), [("c/kWh", 2), ("NZD/kWh", 4)])
async def test_cost_sensors_suggest_display_precision(
    hass, mock_entry, price_unit, precision
) -> None:
    """Cost sensors show cents to 2 decimals and NZD to 4."""
    subentry = create_mock_market_node_subentry(
        enable_accounting=True, price_unit=price_unit
    )
    coordinator = ElectricityInfoCoordinator(hass, mock_entry)
    daily = DailyImportCostSensor(coordinator, mock_entry, subentry)
    sensors = [
        ImportCostSensor(coordinator, mock_entry, subentry),
        daily,
        PreviousDayImportCostSensor(
            coordinator, mock_entry, subentry, daily_sensor=daily
        ),
    ]

    assert [s.suggested_display_precision for s in sensors] == [precision] * 3


def _settled_node_data() -> dict:
    """Build node data with one settled accounting period."""
    accounting = SimpleNamespace(
        prices=[
            SimpleNamespace(
                trading_datetime=dt_util.utcnow() - timedelta(minutes=10),
                trading_period=20,
                price=0.25,
            )
        ]
    )
    return {"accounting": accounting}
