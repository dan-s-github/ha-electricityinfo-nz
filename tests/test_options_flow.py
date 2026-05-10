"""Tests for the SensorSubentryFlowHandler (add / reconfigure sensor subentries)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_FORWARD_PRICES_COUNT,
    CONF_MARKET_TYPE,
    CONF_NODE,
    CONF_SCHEDULE_TYPE,
    CONF_SENSOR_NAME,
    DOMAIN,
)
from tests.helpers import create_mock_subentry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Minimal config entry (no sensors) added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def config_entry_one_sensor(hass: HomeAssistant) -> MockConfigEntry:
    """Config entry with one pre-configured sensor subentry."""
    sub = create_mock_subentry(
        subentry_id="existing_sub_01",
        title="HAY2201 RTD (E)",
        schedule_type="RTD",
        market_type="E",
        node="HAY2201",
        forward_prices_count=24,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
        subentries_data=[
            {
                "data": dict(sub.data),
                "subentry_type": "sensor",
                "title": sub.title,
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    return entry


_VALID_SENSOR_INPUT = {
    CONF_SENSOR_NAME: "Auckland Daily Prices",
    CONF_SCHEDULE_TYPE: "RTD",
    CONF_MARKET_TYPE: "E",
    CONF_NODE: "HAY2201",
    CONF_FORWARD_PRICES_COUNT: 24,
}


# ---------------------------------------------------------------------------
# Add sensor — user flow
# ---------------------------------------------------------------------------


async def test_subentry_flow_shows_user_form(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Starting the user flow returns a FORM with step_id 'user'."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_add_sensor_valid_creates_subentry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Valid input creates a new sensor subentry with the correct title."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=_VALID_SENSOR_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Auckland Daily Prices · HAY2201 RTD (E)"

    # Subentry should now be stored on the config entry
    subentries = [
        s for s in config_entry.subentries.values() if s.subentry_type == "sensor"
    ]
    assert len(subentries) == 1
    assert subentries[0].data[CONF_NODE] == "HAY2201"
    assert subentries[0].data[CONF_SCHEDULE_TYPE] == "RTD"


async def test_add_sensor_auto_title_without_name(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """When no name is given the title is derived from node/schedule/market."""
    input_no_name = {
        k: v for k, v in _VALID_SENSOR_INPUT.items() if k != CONF_SENSOR_NAME
    }
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input={**input_no_name, CONF_SENSOR_NAME: ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HAY2201 RTD (E)"


async def test_add_sensor_data_stored_correctly(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Sensor data dict matches submitted form fields."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], user_input=_VALID_SENSOR_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    subentry = next(iter(config_entry.subentries.values()))
    assert subentry.data[CONF_SCHEDULE_TYPE] == "RTD"
    assert subentry.data[CONF_MARKET_TYPE] == "E"
    assert subentry.data[CONF_NODE] == "HAY2201"
    assert subentry.data[CONF_FORWARD_PRICES_COUNT] == 24
    assert subentry.data.get(CONF_SENSOR_NAME) == "Auckland Daily Prices"


# ---------------------------------------------------------------------------
# add_sensor — validation errors
# ---------------------------------------------------------------------------


async def test_add_sensor_invalid_node_rejected(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """An unrecognised market node is rejected by schema validation (SelectSelector)."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**_VALID_SENSOR_INPUT, CONF_NODE: "INVALID_NODE"},
        )


async def test_add_sensor_invalid_schedule_type_rejected(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """An unrecognised schedule type is rejected by the SelectSelector schema."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**_VALID_SENSOR_INPUT, CONF_SCHEDULE_TYPE: "bad_schedule"},
        )


async def test_add_sensor_invalid_market_type_rejected(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """An unrecognised market type is rejected by the SelectSelector schema."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={**_VALID_SENSOR_INPUT, CONF_MARKET_TYPE: "bad_market"},
        )


# ---------------------------------------------------------------------------
# Reconfigure (edit) sensor
# ---------------------------------------------------------------------------


async def test_reconfigure_sensor_shows_prefilled_form(
    hass: HomeAssistant, config_entry_one_sensor: MockConfigEntry
) -> None:
    """Reconfigure flow opens a FORM pre-filled with current sensor data."""
    subentry_id = next(iter(config_entry_one_sensor.subentries))

    result = await hass.config_entries.subentries.async_init(
        (config_entry_one_sensor.entry_id, "sensor"),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_sensor_updates_subentry(
    hass: HomeAssistant, config_entry_one_sensor: MockConfigEntry
) -> None:
    """Submitting valid reconfigure input updates the subentry and aborts."""
    subentry_id = next(iter(config_entry_one_sensor.subentries))

    result = await hass.config_entries.subentries.async_init(
        (config_entry_one_sensor.entry_id, "sensor"),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": subentry_id,
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_SENSOR_NAME: "Updated Name",
            CONF_SCHEDULE_TYPE: "RTD",
            CONF_MARKET_TYPE: "E",
            CONF_NODE: "BEN2201",
            CONF_FORWARD_PRICES_COUNT: 48,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated = config_entry_one_sensor.subentries[subentry_id]
    assert updated.data[CONF_NODE] == "BEN2201"
    assert updated.data[CONF_SCHEDULE_TYPE] == "RTD"
    assert updated.data[CONF_FORWARD_PRICES_COUNT] == 48
    assert updated.title == "Updated Name · BEN2201 RTD (E)"


async def test_multiple_subentries_added_via_flow(
    hass: HomeAssistant, config_entry_one_sensor: MockConfigEntry
) -> None:
    """Test adding a second sensor subentry via flow (T027 multi-subentry coverage)."""
    entry = config_entry_one_sensor

    # Add first sensor via flow (already exists in fixture)
    assert len(entry.subentries) == 1

    # Add a second sensor via flow
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "sensor"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_SENSOR_NAME: "BEN Market",
            CONF_SCHEDULE_TYPE: "RTD",
            CONF_MARKET_TYPE: "E",
            CONF_NODE: "BEN2201",
            CONF_FORWARD_PRICES_COUNT: 24,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify the second subentry was created
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert len(entry.subentries) == 2

    subentry_ids = {s.subentry_id for s in entry.subentries.values()}
    assert len(subentry_ids) == 2

    nodes = {s.data[CONF_NODE] for s in entry.subentries.values()}
    assert "HAY2201" in nodes
    assert "BEN2201" in nodes
