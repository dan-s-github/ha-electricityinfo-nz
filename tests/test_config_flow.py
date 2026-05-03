"""Test the Electricityinfo NZ config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.electricityinfo_nz.const import DOMAIN


async def test_async_step_user_create_entry(hass: HomeAssistant) -> None:
    """Test user step creates an entry with a generated unique id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"name": "Living Room"},
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"name": "Living Room"}
    assert result2["result"].unique_id == "living_room"


async def test_async_step_user_already_configured(hass: HomeAssistant) -> None:
    """Test second flow aborts when name-derived unique id already exists."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"name": "Living Room"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result3["type"] is FlowResultType.FORM

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={"name": "Living Room"},
    )

    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "already_configured"
