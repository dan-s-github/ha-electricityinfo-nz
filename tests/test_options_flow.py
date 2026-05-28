"""Tests for the MarketNodeSubentryFlow (reconfigure market_node subentries)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
)
from tests.helpers import create_mock_market_node_subentry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
def config_entry_one_market_node(hass: HomeAssistant) -> MockConfigEntry:
    """Config entry with one pre-configured market_node subentry."""
    sub = create_mock_market_node_subentry(
        subentry_id="market_node_1",
        title="HAY2201 [c/kWh]",
        node="HAY2201",
        price_unit="c/kWh",
        enable_live_price=True,
        enable_forecast=False,
        enable_accounting=False,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
        subentries_data=[
            {
                "subentry_id": sub.subentry_id,
                "data": dict(sub.data),
                "subentry_type": "market_node",
                "title": sub.title,
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure_market_node_noop_preserves_data(
    hass: HomeAssistant, config_entry_one_market_node: MockConfigEntry
) -> None:
    """No-op market-node reconfigure aborts successfully without data changes."""
    subentry_id = next(iter(config_entry_one_market_node.subentries))
    original = dict(config_entry_one_market_node.subentries[subentry_id].data)

    result = await hass.config_entries.subentries.async_init(
        (config_entry_one_market_node.entry_id, "market_node"),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated = config_entry_one_market_node.subentries[subentry_id]
    assert dict(updated.data) == original


async def test_reconfigure_market_node_changed_updates_target_only(
    hass: HomeAssistant,
) -> None:
    """Changed market-node reconfigure updates one subentry and keeps others intact."""
    sub1 = create_mock_market_node_subentry(
        subentry_id="market_node_1",
        title="HAY2201 [c/kWh]",
        node="HAY2201",
        price_unit="c/kWh",
        enable_live_price=True,
        enable_forecast=False,
        enable_accounting=False,
    )
    sub2 = create_mock_market_node_subentry(
        subentry_id="market_node_2",
        title="BEN2201 [c/kWh]",
        node="BEN2201",
        price_unit="c/kWh",
        enable_live_price=True,
        enable_forecast=False,
        enable_accounting=False,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
        subentries_data=[
            {
                "subentry_id": sub1.subentry_id,
                "data": dict(sub1.data),
                "subentry_type": "market_node",
                "title": sub1.title,
                "unique_id": None,
            },
            {
                "subentry_id": sub2.subentry_id,
                "data": dict(sub2.data),
                "subentry_type": "market_node",
                "title": sub2.title,
                "unique_id": None,
            },
        ],
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": "market_node_1",
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": True,
            "enable_forecast": True,
            "forecast_type": "price_responsive",
            "forecast_horizons": ["day_ahead"],
            "forecast_retention_hours": "24",
            "enable_accounting": False,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_1 = entry.subentries["market_node_1"]
    unchanged_2 = entry.subentries["market_node_2"]
    assert updated_1.data["price_unit"] == "NZD/kWh"
    assert updated_1.data["enable_forecast"] is True
    assert unchanged_2.data["node"] == "BEN2201"
    assert unchanged_2.data["enable_forecast"] is False
