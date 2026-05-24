"""Tests for migration helpers in integration init module."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.electricityinfo import (
    _build_migrated_node_data,
    _migrate_legacy_schedule,
    async_migrate_entry,
)


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        ("PRSL", (True, "price_responsive", ["day_ahead"])),
        ("PRSS", (True, "price_responsive", ["intraday"])),
        ("NRSL", (True, "non_responsive", ["day_ahead"])),
        ("NRSS", (True, "non_responsive", ["intraday"])),
        ("RTD", (False, None, [])),
    ],
)
def test_migrate_legacy_schedule_mapping(schedule: str, expected: tuple) -> None:
    """Legacy schedule types map to expected 003 forecast settings."""
    assert _migrate_legacy_schedule(schedule) == expected


def test_build_migrated_node_data_sets_live_enabled() -> None:
    """Migrated node data always enables live price and includes node."""
    data = _build_migrated_node_data({"node": "HAY2201", "schedule_type": "PRSL"})
    assert data["node"] == "HAY2201"
    assert data["enable_live_price"] is True
    assert data["enable_forecast"] is True
    assert data["forecast_type"] == "price_responsive"
    assert data["forecast_horizons"] == ["day_ahead"]


@pytest.mark.asyncio
async def test_async_migrate_entry_updates_version_and_dedupes(hass) -> None:
    """Migration updates entry version and tolerates duplicate legacy nodes."""
    subentry_1 = SimpleNamespace(
        subentry_type="sensor",
        data={"node": "HAY2201", "schedule_type": "PRSL"},
    )
    subentry_2 = SimpleNamespace(
        subentry_type="sensor",
        data={"node": "HAY2201", "schedule_type": "PRSS"},
    )
    entry = MagicMock()
    entry.version = 1
    entry.subentries = {"a": subentry_1, "b": subentry_2}

    hass.config_entries.async_update_entry = MagicMock()
    result = await async_migrate_entry(hass, entry)

    assert result is True
    hass.config_entries.async_update_entry.assert_called_once_with(entry, version=2)
