"""Pytest fixtures for custom integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading integrations from custom_components in tests."""


@pytest.fixture
def mock_oauth_session() -> Generator[MagicMock]:
    """Mock OAuth session for testing."""
    with patch(
        "custom_components.electricityinfo_nz.config_flow.requests_oauthlib.OAuth2Session"
    ) as mock:
        session = MagicMock()
        session.authorization_url.return_value = (
            "https://provider.com/authorize?state=test",
            "test_state",
        )
        session.fetch_token = AsyncMock(
            return_value={
                "access_token": "test_token_123",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        )
        mock.return_value = session
        yield session


@pytest.fixture
def mock_wrapper() -> Generator[AsyncMock]:
    """Mock electricityinfo-nz wrapper for testing."""
    with patch(
        "custom_components.electricityinfo_nz.config_flow.ElectricityinfoNZ"
    ) as mock:
        wrapper = AsyncMock()
        wrapper.validate_token = AsyncMock(return_value=True)
        mock.return_value = wrapper
        yield wrapper


@pytest.fixture
def mock_wrapper_invalid() -> Generator[AsyncMock]:
    """Mock wrapper that returns invalid token."""
    with patch(
        "custom_components.electricityinfo_nz.config_flow.ElectricityinfoNZ"
    ) as mock:
        wrapper = AsyncMock()
        wrapper.validate_token = AsyncMock(side_effect=Exception("Invalid token"))
        mock.return_value = wrapper
        yield wrapper
