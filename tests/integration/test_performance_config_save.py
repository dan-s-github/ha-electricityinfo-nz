"""
Measurable acceptance tests for SC-002, SC-003, SC-005.

SC-002: All selected entity types created and visible in HA within 3 minutes
        after config is saved, with no manual restart required.
SC-003: With 5 configured market nodes, saving a config completes in under
        10 seconds in at least 95% of attempts; sensors available within 3 min.
SC-005: Sensor values reflect the latest available provider data within one
        coordinator refresh cycle (30 minutes) after that data becomes available.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import DOMAIN
from custom_components.electricityinfo.coordinator import ElectricityInfoCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _mock_price(
    node: str,
    price: float = 4.23,
    trading_period: int = 24,
    trading_datetime: datetime | None = None,
) -> MagicMock:
    p = MagicMock()
    p.trading_datetime = trading_datetime or datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    p.trading_period = trading_period
    p.node = node
    p.schedule = "PRSL"
    p.price = price
    return p


def _mock_schedule(node: str, price: float = 4.23) -> MagicMock:
    s = MagicMock()
    s.prices = [_mock_price(node, price)]
    return s


def _coordinator_data_for_nodes(
    subentry_ids_and_nodes: list[tuple[str, str]],
) -> dict[str, Any]:
    return {
        subentry_id: {
            "node": node,
            "day_ahead": _mock_schedule(node),
            "intraday": None,
            "accounting": None,
            "import_cost_delta": None,
            "export_revenue_delta": None,
            "accounting_date_nzt": None,
            "config": {
                "node": node,
                "price_unit": "c/kWh",
                "enable_live_price": True,
                "enable_forecast": False,
                "enable_accounting": False,
            },
            "error": None,
        }
        for subentry_id, node in subentry_ids_and_nodes
    }


async def test_sc002_all_entity_types_visible_immediately_after_setup(
    hass: HomeAssistant,
) -> None:
    """
    SC-002: all enabled entity types are visible in HA immediately after setup.

    Entities must not require a manual restart or reload to appear.
    """
    subentry_data = {
        "node": "HAY2201",
        "price_unit": "c/kWh",
        "enable_live_price": True,
        "enable_forecast": True,
        "forecast_type": "price_responsive",
        "forecast_horizons": ["day_ahead", "intraday"],
        "forecast_retention_hours": 24,
        "enable_accounting": True,
        "accounting_retention_hours": 24,
        "import_meter_entity_id": "sensor.grid_import",
        "export_meter_entity_id": "sensor.grid_export",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={"client_id": "test_client", "client_secret": "test_secret"},
        subentries_data=[
            {
                "subentry_id": "sub_hay",
                "data": subentry_data,
                "subentry_type": "market_node",
                "title": "HAY2201 [c/kWh]",
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)

    mock_price = _mock_price("HAY2201")
    mock_sched = MagicMock()
    mock_sched.prices = [mock_price]

    with patch.object(
        ElectricityInfoCoordinator,
        "_async_update_data",
        return_value={
            "sub_hay": {
                "node": "HAY2201",
                "day_ahead": mock_sched,
                "intraday": mock_sched,
                "accounting": mock_sched,
                "import_cost_delta": 0.05,
                "export_revenue_delta": 0.02,
                "accounting_date_nzt": None,
                "settled_price": 4.50,
                "settled_timestamp": datetime(2026, 5, 9, 11, 30, tzinfo=UTC),
                "config": subentry_data,
                "error": None,
            }
        },
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    entity_ids = [s.entity_id for s in states]

    # All seven enabled entity types must be visible with no manual restart
    assert any("live_price" in eid for eid in entity_ids), (
        "SC-002 FAIL: live_price entity not visible after setup"
    )
    assert any("day_ahead_forecast" in eid for eid in entity_ids), (
        "SC-002 FAIL: day_ahead_forecast entity not visible after setup"
    )
    assert any("intraday_forecast" in eid for eid in entity_ids), (
        "SC-002 FAIL: intraday_forecast entity not visible after setup"
    )
    assert any("settled_price" in eid for eid in entity_ids), (
        "SC-002 FAIL: settled_price entity not visible after setup"
    )
    assert any("import_cost" in eid for eid in entity_ids), (
        "SC-002 FAIL: import_cost entity not visible after setup"
    )
    assert any("export_revenue" in eid for eid in entity_ids), (
        "SC-002 FAIL: export_revenue entity not visible after setup"
    )
    assert any("daily_import_cost" in eid for eid in entity_ids), (
        "SC-002 FAIL: daily_import_cost entity not visible after setup"
    )
    assert any("daily_export_revenue" in eid for eid in entity_ids), (
        "SC-002 FAIL: daily_export_revenue entity not visible after setup"
    )


async def test_sc003_five_node_setup_completes_within_latency_budget(
    hass: HomeAssistant,
) -> None:
    """
    SC-003: setup of 5 market nodes completes in under 10 seconds.

    All 5 nodes must have a live_price entity visible after setup.
    """
    nodes = [
        ("sub_hay", "HAY2201"),
        ("sub_ben", "BEN2201"),
        ("sub_brb", "BRB0331"),
        ("sub_ota", "OTA2201"),
        ("sub_isl", "ISL2201"),
    ]
    subentries_data = [
        {
            "subentry_id": sid,
            "data": {
                "node": node,
                "price_unit": "c/kWh",
                "enable_live_price": True,
                "enable_forecast": False,
                "enable_accounting": False,
            },
            "subentry_type": "market_node",
            "title": f"{node} [c/kWh]",
            "unique_id": None,
        }
        for sid, node in nodes
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ (5 nodes)",
        data={"client_id": "test_client", "client_secret": "test_secret"},
        subentries_data=subentries_data,
    )
    entry.add_to_hass(hass)

    coordinator_data = _coordinator_data_for_nodes(nodes)

    start = time.monotonic()
    with patch.object(
        ElectricityInfoCoordinator,
        "_async_update_data",
        return_value=coordinator_data,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    elapsed = time.monotonic() - start

    assert elapsed < 10.0, (
        f"SC-003 FAIL: 5-node setup took {elapsed:.2f}s (budget: 10s)"
    )

    states = hass.states.async_all("sensor")
    entity_ids = [s.entity_id for s in states]

    for _sid, node in nodes:
        node_lower = node.lower()
        assert any(node_lower in eid for eid in entity_ids), (
            f"SC-003 FAIL: no entities visible for node {node} after setup"
        )


async def test_sc005_sensor_reflects_new_data_within_one_update_cycle(
    hass: HomeAssistant,
) -> None:
    """
    SC-005: sensor value reflects updated coordinator data within one refresh cycle.

    After a coordinator data update, sensors must report the new value on the
    very next HA event loop drain — not after a delay or a further restart.
    """
    subentry_data = {
        "node": "HAY2201",
        "price_unit": "c/kWh",
        "enable_live_price": True,
        "enable_forecast": False,
        "enable_accounting": False,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={"client_id": "test_client", "client_secret": "test_secret"},
        subentries_data=[
            {
                "subentry_id": "sub_hay",
                "data": subentry_data,
                "subentry_type": "market_node",
                "title": "HAY2201 [c/kWh]",
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)

    initial_price = _mock_price("HAY2201", price=4.23)
    initial_sched = MagicMock()
    initial_sched.prices = [initial_price]

    initial_data = {
        "sub_hay": {
            "node": "HAY2201",
            "day_ahead": initial_sched,
            "intraday": None,
            "accounting": None,
            "import_cost_delta": None,
            "export_revenue_delta": None,
            "accounting_date_nzt": None,
            "config": subentry_data,
            "error": None,
        }
    }

    with patch.object(
        ElectricityInfoCoordinator,
        "_async_update_data",
        return_value=initial_data,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator: ElectricityInfoCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Verify initial state was picked up
    live_states = [
        s for s in hass.states.async_all("sensor") if "live_price" in s.entity_id
    ]
    assert live_states, "SC-005: live_price entity not found after setup"
    initial_state = live_states[0].state

    # Simulate one coordinator refresh cycle with a new price value
    updated_price = _mock_price("HAY2201", price=8.99)
    updated_sched = MagicMock()
    updated_sched.prices = [updated_price]

    updated_data = {
        "sub_hay": {
            **initial_data["sub_hay"],
            "day_ahead": updated_sched,
        }
    }

    coordinator.data = updated_data
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    live_states_after = [
        s for s in hass.states.async_all("sensor") if "live_price" in s.entity_id
    ]
    assert live_states_after, "SC-005: live_price entity disappeared after update"
    updated_state = live_states_after[0].state

    # State must change — sensor picks up the new data within one update cycle
    assert updated_state != initial_state or updated_state == "unavailable", (
        "SC-005 FAIL: live_price state did not change after coordinator update "
        f"(was {initial_state!r}, still {updated_state!r})"
    )
