"""Tests for multiple market-node sensors configuration and operation."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo import ElectricityInfoCoordinator
from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
)
from custom_components.electricityinfo.sensor import DayAheadForecastSensor
from tests.helpers import create_mock_market_node_subentry


async def test_five_sensors_no_performance_degradation(hass) -> None:
    """SC-005: Test 5+ simultaneous market-node sensors without degradation."""
    subentries_data = []
    nodes = ["HAY2201", "BEN2201", "OTA0011", "TWI0331", "CEN0011"]
    for i, node in enumerate(nodes):
        sub = create_mock_market_node_subentry(
            subentry_id=f"market_node_{i}",
            title=f"{node} [c/kWh]",
            node=node,
            price_unit="c/kWh",
            enable_live_price=True,
            enable_forecast=False,
            enable_accounting=False,
        )
        subentries_data.append(
            {
                "data": dict(sub.data),
                "subentry_type": "market_node",
                "title": sub.title,
                "unique_id": None,
            }
        )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Main",
        data={
            CONF_CLIENT_ID: "test_client",
            CONF_CLIENT_SECRET: "test_secret",
        },
        subentries_data=subentries_data,
    )
    entry.add_to_hass(hass)

    with patch.object(
        ElectricityInfoCoordinator, "_async_update_data", return_value={}
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    states = hass.states.async_all("sensor")
    assert len(states) >= 5, f"Expected >=5 sensor entities, got {len(states)}"

    for node in nodes:
        live_entity = next(
            (
                s
                for s in states
                if node.lower() in s.entity_id and "live_price" in s.entity_id
            ),
            None,
        )
        assert live_entity is not None, f"Missing live_price entity for {node}"

    entity_ids = [s.entity_id for s in states]
    assert len(entity_ids) == len(set(entity_ids)), "Duplicate entity IDs detected"


@pytest.mark.asyncio
async def test_forecast_history_respects_retention_window(hass) -> None:
    """US2 retention keeps only retention_hours*2 history points."""
    subentry = create_mock_market_node_subentry(
        enable_live_price=False,
        enable_forecast=True,
        forecast_horizons=["day_ahead"],
        forecast_retention_hours=6,
    )
    now = datetime(2026, 5, 24, 12, 0, tzinfo=UTC)

    def _price(offset_minutes: int, period: int, value: float) -> MagicMock:
        item = MagicMock()
        item.trading_datetime = now + timedelta(minutes=offset_minutes)
        item.trading_period = period
        item.node = "HAY2201"
        item.schedule = "PRSL"
        item.price = value
        return item

    schedule = MagicMock()
    # 16 history points + 1 future point, retention=6h => keep latest 12 history points.
    schedule.prices = [
        _price(-(16 - idx) * 30, idx + 1, float(idx + 1)) for idx in range(16)
    ] + [_price(30, 99, 99.0)]

    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.title = "Electricity Info NZ"
    entry.data = {
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
    }
    entry.subentries = {subentry.subentry_id: subentry}

    with patch("custom_components.electricityinfo.AsyncMarketPricesClient"):
        coordinator = ElectricityInfoCoordinator(hass, entry)
        coordinator.last_update_success = True
        coordinator.data = {
            subentry.subentry_id: {
                "day_ahead": schedule,
                "intraday": None,
                "accounting": None,
                "config": dict(subentry.data),
                "error": None,
            }
        }
        entity = DayAheadForecastSensor(coordinator, entry, subentry)
        with (
            patch("homeassistant.util.dt.utcnow", return_value=now),
            patch.object(entity, "async_write_ha_state", MagicMock()),
        ):
            entity._handle_coordinator_update()

    history_periods = [
        p["trading_period"] for p in entity.extra_state_attributes["history"]
    ]
    assert len(history_periods) == 12
    assert history_periods == list(range(5, 17))
