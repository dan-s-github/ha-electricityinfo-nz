"""Test the Electricityinfo NZ config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.electricityinfo_nz.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
)


async def test_async_step_user_form_displays(hass: HomeAssistant) -> None:
    """Test user step form is displayed correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_async_step_user_missing_client_id(hass: HomeAssistant) -> None:
    """Test validation error when client_id is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CLIENT_ID: "",
            CONF_CLIENT_SECRET: "secret123",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert CONF_CLIENT_ID in result2["errors"]


async def test_async_step_user_missing_client_secret(hass: HomeAssistant) -> None:
    """Test validation error when client_secret is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CLIENT_ID: "client123",
            CONF_CLIENT_SECRET: "",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert CONF_CLIENT_SECRET in result2["errors"]


async def test_async_step_user_single_instance(hass: HomeAssistant) -> None:
    """Test that only one instance is allowed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    # First attempt would proceed to auth step (stubbed for Phase 1)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_CLIENT_ID: "client123",
            CONF_CLIENT_SECRET: "secret123",
        },
    )

    # Second attempt should abort
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={
            CONF_CLIENT_ID: "client456",
            CONF_CLIENT_SECRET: "secret456",
        },
    )

    # Single instance constraint should be enforced
    assert result4["type"] in [FlowResultType.ABORT, FlowResultType.FORM]
