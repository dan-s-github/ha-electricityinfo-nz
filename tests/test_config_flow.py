"""Test the Electricityinfo NZ config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from electricityinfo_nz.exceptions import AuthenticationError, TransportError
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
)


def _patch_client() -> patch:
    """Patch AsyncMarketPricesClient in config flow."""
    return patch(
        "custom_components.electricityinfo.config_flow.AsyncMarketPricesClient"
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

    client_patch = _patch_client()
    # First attempt should create config entry
    with client_patch as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_schedules.return_value = {"schedules": []}
        mock_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CLIENT_ID: "client123",
                CONF_CLIENT_SECRET: "secret123",
            },
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY

    # Second attempt should abort immediately at init (single_config_entry=true)
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "single_instance_allowed"


async def test_token_exchange_success(hass: HomeAssistant) -> None:
    """Test successful token exchange and validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    client_patch = _patch_client()
    with client_patch as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_schedules.return_value = {"schedules": []}
        mock_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CLIENT_ID: "client123",
                CONF_CLIENT_SECRET: "secret123",
            },
        )

        # Should create config entry
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Electricityinfo NZ"
        assert result2["data"][CONF_CLIENT_ID] == "client123"
        assert result2["data"][CONF_CLIENT_SECRET] == "secret123"


async def test_token_exchange_invalid_credentials(hass: HomeAssistant) -> None:
    """Test token exchange fails with invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    client_patch = _patch_client()
    with client_patch as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_schedules.side_effect = AuthenticationError(
            "Invalid credentials"
        )
        mock_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CLIENT_ID: "invalid_client",
                CONF_CLIENT_SECRET: "invalid_secret",
            },
        )

        # Should return to user step with error
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "user"
        assert "base" in result2["errors"]
        assert result2["errors"]["base"] == "invalid_auth"


async def test_token_validation_network_error(hass: HomeAssistant) -> None:
    """Test token validation with network error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    client_patch = _patch_client()
    with client_patch as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_schedules.side_effect = TransportError("Network error")
        mock_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CLIENT_ID: "client123",
                CONF_CLIENT_SECRET: "secret123",
            },
        )

        # Should show retry form
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "auth_validate"
        assert "base" in result2["errors"]
        assert result2["errors"]["base"] == "cannot_connect"


async def test_token_validation_retry_success(hass: HomeAssistant) -> None:
    """Test token validation succeeds after retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    # First attempt: network error
    client_patch = _patch_client()
    with client_patch as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_schedules.side_effect = TimeoutError("Timeout")
        mock_client.return_value = mock_client_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CLIENT_ID: "client123",
                CONF_CLIENT_SECRET: "secret123",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "auth_validate"

    # Second attempt: success
    client_patch = _patch_client()
    with client_patch as mock_client:
        mock_client_instance = AsyncMock()
        mock_client_instance.get_schedules.return_value = {"schedules": []}
        mock_client.return_value = mock_client_instance

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
        )

        # Should create config entry on retry success
        assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_market_node_live_only_subentry_creation(hass: HomeAssistant) -> None:
    """Live-only market node subentry can be created."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_market_node_forecast_requires_horizon_when_enabled(
    hass: HomeAssistant,
) -> None:
    """Forecast-enabled form requires at least one horizon."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={"source": config_entries.SOURCE_USER},
    )

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": False,
            "enable_forecast": True,
            "forecast_type": "price_responsive",
            "forecast_horizons": [],
            "forecast_retention_hours": "24",
            "enable_accounting": False,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["forecast_horizons"] == "forecast_horizons_empty"


async def test_market_node_forecast_type_schema_validation(
    hass: HomeAssistant,
) -> None:
    """Forecast type selector rejects unsupported values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={"source": config_entries.SOURCE_USER},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                "node": "HAY2201",
                "price_unit": "c/kWh",
                "enable_live_price": False,
                "enable_forecast": True,
                "forecast_type": "unexpected",
                "forecast_horizons": ["day_ahead"],
                "forecast_retention_hours": "24",
                "enable_accounting": False,
            },
        )


async def test_market_node_forecast_retention_validation(
    hass: HomeAssistant,
) -> None:
    """Forecast retention selector rejects unsupported values."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={"source": config_entries.SOURCE_USER},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input={
                "node": "HAY2201",
                "price_unit": "c/kWh",
                "enable_live_price": False,
                "enable_forecast": True,
                "forecast_type": "price_responsive",
                "forecast_horizons": ["day_ahead"],
                "forecast_retention_hours": "5",
                "enable_accounting": False,
            },
        )


async def test_market_node_forecast_persists_horizons_and_retention(
    hass: HomeAssistant,
) -> None:
    """Forecast settings are normalized and persisted."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={"source": config_entries.SOURCE_USER},
    )

    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "node": "HAY2201",
            "price_unit": "NZD/kWh",
            "enable_live_price": False,
            "enable_forecast": True,
            "forecast_type": "non_responsive",
            "forecast_horizons": ["intraday", "day_ahead", "intraday"],
            "forecast_retention_hours": "12",
            "enable_accounting": False,
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"]["forecast_type"] == "non_responsive"
    assert result2["data"]["forecast_horizons"] == ["day_ahead", "intraday"]
    assert result2["data"]["forecast_retention_hours"] == 12


async def test_market_node_duplicate_node_rejected_on_create(
    hass: HomeAssistant,
) -> None:
    """Adding another subentry for the same node is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
        subentries_data=[
            {
                "subentry_id": "market_node_1",
                "subentry_type": "market_node",
                "title": "HAY2201 [c/kWh]",
                "data": {
                    "node": "HAY2201",
                    "price_unit": "c/kWh",
                    "enable_live_price": True,
                    "enable_forecast": False,
                    "enable_accounting": False,
                },
                "unique_id": None,
            }
        ],
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={"source": config_entries.SOURCE_USER},
    )
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["node"] == "node_already_configured"


async def test_market_node_duplicate_node_rejected_on_reconfigure(
    hass: HomeAssistant,
) -> None:
    """Reconfiguring to a node already used by another subentry is rejected."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electricityinfo NZ",
        data={CONF_CLIENT_ID: "client123", CONF_CLIENT_SECRET: "secret123"},
        subentries_data=[
            {
                "subentry_id": "market_node_1",
                "subentry_type": "market_node",
                "title": "HAY2201 [c/kWh]",
                "data": {
                    "node": "HAY2201",
                    "price_unit": "c/kWh",
                    "enable_live_price": True,
                    "enable_forecast": False,
                    "enable_accounting": False,
                },
                "unique_id": None,
            },
            {
                "subentry_id": "market_node_2",
                "subentry_type": "market_node",
                "title": "BEN2201 [c/kWh]",
                "data": {
                    "node": "BEN2201",
                    "price_unit": "c/kWh",
                    "enable_live_price": True,
                    "enable_forecast": False,
                    "enable_accounting": False,
                },
                "unique_id": None,
            },
        ],
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "market_node"),
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "subentry_id": "market_node_2",
        },
    )
    result2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            "node": "HAY2201",
            "price_unit": "c/kWh",
            "enable_live_price": True,
            "enable_forecast": False,
            "enable_accounting": False,
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["node"] == "node_already_configured"
