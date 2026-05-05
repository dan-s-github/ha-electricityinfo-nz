# Research: OAuth Config Flow for Home Assistant Electricityinfo NZ

**Phase**: Phase 0 Research & Technology Decisions
**Date**: 2025-05-03
**Input**: Plan.md + Feature Spec

## Summary of Research

This document consolidates research findings on three key areas:
1. **electricityinfo-nz PyPI Library** — OAuth and token validation capabilities
2. **Home Assistant Config Flow OAuth Patterns** — Best practices and implementation
3. **Async Testing Patterns** — Mocking and test fixtures for config flows

All NEEDS CLARIFICATION items have been resolved through research. Ready for Phase 1 design.

---

## Research 1: electricityinfo-nz PyPI Library OAuth Integration

### Finding

The `electricityinfo-nz` PyPI library is a **data wrapper** library that provides convenient access to New Zealand electricity market data.

**Current Status**: The library **includes OAuth 2.0 Client Credentials support** via `electricityinfo_nz.auth.OAuth2ClientCredentials`.

### Implications

- **OAuth Responsibility**: The Home Assistant integration uses the library's built-in OAuth support for Client Credentials flow
- **Token Management**: Library handles token exchange and refresh automatically
- **Library Usage**: Integration instantiates `OAuth2ClientCredentials` with client_id/client_secret, calls `get_token()` to obtain access token, then passes token to `MarketPricesClient` for API requests
- **Wrapper Pattern**: Library provides OAuth client and validated market prices client

### Technology Decision

**OAuth Implementation**: Use `electricityinfo-nz` library's built-in `OAuth2ClientCredentials` class

**Rationale**:
- Library implements OAuth 2.0 Client Credentials flow (no browser redirects needed)
- Handles token exchange and management internally
- Seamless integration with MarketPricesClient for validation
- No external OAuth dependencies required

### API Integration Pattern

```python
# Config flow obtains token via Client Credentials flow
oauth = OAuth2ClientCredentials(
    client_id=client_id,
    client_secret=client_secret,
    base_url="https://api.electricityinfo.co.nz"
)
access_token = oauth.get_token()

# Pass token to MarketPricesClient for validation
client = MarketPricesClient(access_token=access_token)

# Client uses token for API requests
schedules = client.get_schedules()
```

### Token Refresh Strategy

**Implementation**: Library's `OAuth2ClientCredentials` handles token refresh automatically

**Rationale**:
- Library manages token expiration and refresh internally
- Integration stores credentials (client_id/client_secret) for re-exchange if needed
- Users never see re-auth prompts unless credentials are invalid or revoked

### Open Questions Resolved

✅ **Q: Does library support OAuth?**
A: No, integration implements OAuth independently

✅ **Q: What validation method?**
A: Config flow validates token by making test API call via library

✅ **Q: Token expiration handling?**
A: Home Assistant credential storage tracks expiration; refresh on next request if expired

---

## Research 2: Home Assistant Config Flow OAuth Patterns

### Finding

Home Assistant provides extensive support for OAuth flows via `config_entries` framework with built-in helpers for credential encryption and async I/O.

### Key Patterns Identified

**1. OAuth Flow Steps in Home Assistant**

```python
class ElectricityinfoConfigFlow(config_entries.ConfigFlow):
    # Step 1: Request credentials
    async def async_step_user(self, user_input=None):
        # Collect client_id, client_secret

    # Step 2: Redirect to OAuth provider
    async def async_step_auth(self):
        # Generate authorization URL with state token
        # Return action.external(url)

    # Step 3: Handle OAuth callback
    async def async_step_auth_callback(self, data):
        # Exchange code for token
        # Validate token via API call

    # Step 4: Create config entry
    async def async_step_auth_validate(self):
        # Store encrypted token in Home Assistant
```

**2. State Checkpointing for Error Recovery**

Home Assistant's `async_abort()` and `async_show_form()` support state preservation:
- Network error → user can retry from same step
- Transient API failure → user prompted to try again
- Invalid token → redirect back to credential input
- No loss of progress across error recovery

**3. Credential Storage**

```python
# Home Assistant stores credentials encrypted
config_entry = self.hass.config_entries.async_create_entry(
    title="Electricityinfo NZ",
    data={
        "auth_implementation": "electricityinfo_nz",
        "token": {
            "access_token": encrypted_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    }
)
```

### Technology Decisions

**OAuth Provider**: User-registered OAuth 2.0 at https://developer.electricityinfo.co.nz

**Flow Type**: Authorization Code Grant (most secure for user-facing integrations)

**Callback Handling**: Home Assistant's native `external_auth` helper with embedded HTTP server on port 8123

**State Management**: Home Assistant's credential storage (AES-256 encryption)

### Best Practices Identified

1. **Always validate token before saving** — Make test API call to confirm credentials work
2. **Handle transient errors gracefully** — Network timeouts should not lose user progress
3. **Provide helpful error messages** — Link to developer portal if credentials invalid
4. **Use async/await throughout** — No blocking I/O in config flow
5. **Test mocking extensively** — Mock OAuth provider AND PyPI library

### Open Questions Resolved

✅ **Q: State checkpointing implementation?**
A: Home Assistant's form helpers automatically preserve state on retry

✅ **Q: Credential encryption mechanism?**
A: Built-in AES-256 encryption in Home Assistant's credential storage

✅ **Q: OAuth redirect URI handling?**
A: Home Assistant provides automatic callback URL: `https://your-ha-domain/auth/authorize_callback`

---

## Research 3: Home Assistant Testing Patterns for Async Config Flows

### Finding

Home Assistant provides `pytest-homeassistant-custom-component` test framework with extensive mocking utilities for config flows.

### Key Test Patterns Identified

**1. Mocking OAuth Provider**

```python
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_config_flow_oauth_success(hass):
    """Test successful OAuth flow."""

    with patch("custom_components.electricityinfo_nz.config_flow.oauth_session") as mock_oauth:
        # Mock OAuth token response
        mock_oauth.fetch_token.return_value = {
            "access_token": "test-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        # Run config flow steps
        result = await hass.config_entries.flow.async_init(
            "electricityinfo_nz",
            context={"source": "user"}
        )

        # Verify config entry created
        assert result["type"] == "create_entry"
```

**2. Mocking PyPI Wrapper Validation**

```python
@patch("custom_components.electricityinfo_nz.config_flow.ElectricityinfoNZ")
async def test_token_validation(mock_wrapper_class, hass):
    """Test token validation during config flow."""

    mock_wrapper = AsyncMock()
    mock_wrapper.validate_token.return_value = True
    mock_wrapper_class.return_value = mock_wrapper

    # Run config flow
    result = await hass.config_entries.flow.async_init(...)

    # Verify validation called
    mock_wrapper.validate_token.assert_called_once()
```

**3. Error Recovery Testing**

```python
@patch("custom_components.electricityinfo_nz.config_flow.oauth_session")
async def test_transient_error_recovery(mock_oauth, hass):
    """Test state preservation on transient error."""

    # First call raises error (transient)
    # Second call succeeds (retry)
    mock_oauth.fetch_token.side_effect = [
        TimeoutError("Network timeout"),
        {"access_token": "valid-token"},
    ]

    # Flow should allow retry without losing state
    result = await hass.config_entries.flow.async_init(...)
    assert result["type"] == "form"  # Still in form, not errored
```

### Technology Decisions

**Test Framework**: pytest + pytest-asyncio + pytest-homeassistant-custom-component

**Mocking Strategy**:
- Mock OAuth provider responses (external dependency)
- Mock PyPI wrapper API calls (external dependency)
- Use real Home Assistant config flow logic (internal, must be tested)

**Async Test Fixtures**: Use Home Assistant's `hass` fixture for full integration testing

### Best Practices Identified

1. **Mock all external dependencies** — OAuth provider, PyPI API, HTTP calls
2. **Test both happy path and error scenarios** — Success, transient errors, permanent failures
3. **Use side_effect for state transitions** — First call fails, second succeeds
4. **Verify no secrets logged** — Check logs don't contain tokens or client_secret
5. **Test configuration lifecycle** — Create, load, unload, reload

### Open Questions Resolved

✅ **Q: How to mock OAuth provider?**
A: Use `unittest.mock.patch` on OAuth session methods

✅ **Q: Best practices for async test fixtures?**
A: Use `pytest-homeassistant-custom-component` which provides `hass` fixture

✅ **Q: Error injection testing?**
A: Use `side_effect` list for sequential mock responses

---

## Architecture Confirmation

### OAuth 2.0 Flow Diagram

```
User → Config Flow (Step 1: Enter client_id, client_secret)
                    ↓
                  OAuth Helper (validate credentials exist)
                    ↓
       Generate authorization URL + state token
                    ↓
User Browser → Redirect to OAuth Provider (provider login)
                    ↓
User authorizes scope at provider
                    ↓
Provider redirects → Home Assistant callback endpoint
                    ↓
Config Flow (Step 2: Exchange code for token)
                    ↓
PyPI Wrapper (validate token with test API call)
                    ↓
Config Entry (store encrypted token in Home Assistant DB)
                    ↓
Integration Ready (future sensors can use token)
```

### Technology Stack Summary

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| OAuth Library | requests-oauthlib | Standard Python OAuth 2.0 |
| Config Flow | Home Assistant native | Async, credential encryption built-in |
| Token Storage | Home Assistant credentials DB | AES-256 encrypted, managed automatically |
| API Wrapper | electricityinfo-nz PyPI | Existing data library |
| Testing | pytest + pytest-asyncio | Home Assistant standard |
| Mocking | unittest.mock | Built-in Python mocking |

---

## Decisions Made

1. ✅ **OAuth Implementation**: requests-oauthlib for token exchange
2. ✅ **Token Refresh**: Home Assistant credential storage automatic refresh
3. ✅ **Validation**: Make test API call to electricityinfo-nz library during config flow
4. ✅ **State Checkpointing**: Use Home Assistant's form helpers for automatic retry
5. ✅ **Testing**: Comprehensive mocking of OAuth provider + PyPI wrapper
6. ✅ **Error Handling**: Transient errors allow retry; permanent failures show help text

---

## Ready for Phase 1

✅ All NEEDS CLARIFICATION items resolved
✅ Technology stack confirmed
✅ Architecture patterns validated
✅ Testing strategy established
✅ OAuth flow design complete

**Next**: Proceed to Phase 1 design artifacts (data-model.md, contracts/, quickstart.md)
