"""Integration tests for multi-node market-node setup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import DOMAIN
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator


def _schedule_for_now(node: str, price: float) -> MagicMock:
    """Create a minimal day-ahead schedule aligned to current period."""
    period = MagicMock()
    period.trading_datetime = datetime.now(UTC) - timedelta(minutes=5)
    period.trading_period = 24
    period.node = node
    period.schedule = "PRSL"
    period.price = price
    schedule = MagicMock()
    schedule.prices = [period]
    return schedule


async def test_multi_node_live_sensors_created_with_independent_values(hass) -> None:
    """US4: two nodes create separate live sensors with independent updates."""
    subentry_1 = {
        "node": "HAY2201",
        "price_unit": "c/kWh",
        "enable_live_price": True,
        "enable_forecast": False,
        "enable_accounting": False,
    }
    subentry_2 = {
        "node": "BEN2201",
        "price_unit": "c/kWh",
        "enable_live_price": True,
        "enable_forecast": False,
        "enable_accounting": False,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main",
        data={"client_id": "test_client", "client_secret": "test_secret"},
        subentries_data=[
            {
                "data": subentry_1,
                "subentry_type": "market_node",
                "title": "HAY2201 [c/kWh]",
                "unique_id": None,
                "subentry_id": "market_node_1",
            },
            {
                "data": subentry_2,
                "subentry_type": "market_node",
                "title": "BEN2201 [c/kWh]",
                "unique_id": None,
                "subentry_id": "market_node_2",
            },
        ],
    )
    entry.add_to_hass(hass)

    async def _mock_update_data(_self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for subentry_id, subentry in entry.subentries.items():
            node = subentry.data["node"]
            price = 5.25 if node == "HAY2201" else 7.75
            data[subentry_id] = {
                "node": node,
                "day_ahead": _schedule_for_now(node, price),
                "intraday": None,
                "accounting": None,
                "config": subentry.data,
                "error": None,
            }
        return data

    with patch.object(
        ElectricityInfoCoordinator, "_async_update_data", _mock_update_data
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator: ElectricityInfoCoordinator = hass.data[DOMAIN][entry.entry_id][
            "coordinator"
        ]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    hay_state = next(
        s for s in states if "hay2201" in s.entity_id and "live_price" in s.entity_id
    )
    ben_state = next(
        s for s in states if "ben2201" in s.entity_id and "live_price" in s.entity_id
    )

    assert float(hay_state.state) == 5.25
    assert float(ben_state.state) == 7.75
    assert hay_state.entity_id != ben_state.entity_id
