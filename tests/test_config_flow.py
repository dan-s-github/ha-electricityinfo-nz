"""Test the Electricityinfo NZ config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from electricityinfo_nz.exceptions import AuthenticationError, TransportError
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.electricityinfo.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DOMAIN,
)


def _patch_oauth_and_client() -> tuple:
    """Patch OAuth2ClientCredentials and MarketPricesClient."""
    oauth_patch = patch(
        "custom_components.electricityinfo.config_flow.OAuth2ClientCredentials"
    )
    client_patch = patch(
        "custom_components.electricityinfo.config_flow.MarketPricesClient"
    )
    return oauth_patch, client_patch


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

    oauth_patch, client_patch = _patch_oauth_and_client()
    # First attempt should create config entry
    with oauth_patch as mock_oauth, client_patch as mock_client:
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_token.return_value = "access_token_123"
        mock_oauth.return_value = mock_oauth_instance

        mock_client_instance = MagicMock()
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

    # Second attempt should abort due to single instance constraint
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    oauth_patch, client_patch = _patch_oauth_and_client()
    with oauth_patch as mock_oauth, client_patch as mock_client:
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_token.return_value = "access_token_456"
        mock_oauth.return_value = mock_oauth_instance

        mock_client_instance = MagicMock()
        mock_client_instance.get_schedules.return_value = {"schedules": []}
        mock_client.return_value = mock_client_instance

        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            user_input={
                CONF_CLIENT_ID: "client456",
                CONF_CLIENT_SECRET: "secret456",
            },
        )

        # Single instance constraint should be enforced
        assert result4["type"] is FlowResultType.ABORT


async def test_token_exchange_success(hass: HomeAssistant) -> None:
    """Test successful token exchange and validation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    oauth_patch, client_patch = _patch_oauth_and_client()
    with oauth_patch as mock_oauth, client_patch as mock_client:
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_token.return_value = "access_token_123"
        mock_oauth.return_value = mock_oauth_instance

        mock_client_instance = MagicMock()
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

    oauth_patch, _ = _patch_oauth_and_client()
    with oauth_patch as mock_oauth:
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_token.side_effect = AuthenticationError(
            "Invalid credentials"
        )
        mock_oauth.return_value = mock_oauth_instance

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

    oauth_patch, client_patch = _patch_oauth_and_client()
    with oauth_patch as mock_oauth, client_patch as mock_client:
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_token.return_value = "access_token_123"
        mock_oauth.return_value = mock_oauth_instance

        mock_client_instance = MagicMock()
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
    oauth_patch, client_patch = _patch_oauth_and_client()
    with oauth_patch as mock_oauth, client_patch as mock_client:
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_token.return_value = "access_token_123"
        mock_oauth.return_value = mock_oauth_instance

        mock_client_instance = MagicMock()
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
    oauth_patch, client_patch = _patch_oauth_and_client()
    with oauth_patch as mock_oauth, client_patch as mock_client:
        mock_oauth_instance = MagicMock()
        mock_oauth_instance.get_token.return_value = "access_token_123"
        mock_oauth.return_value = mock_oauth_instance

        mock_client_instance = MagicMock()
        mock_client_instance.get_schedules.return_value = {"schedules": []}
        mock_client.return_value = mock_client_instance

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
        )

        # Should create config entry on retry success
        assert result3["type"] is FlowResultType.CREATE_ENTRY
