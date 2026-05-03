# PyPI Wrapper Integration Contract

**Phase**: Phase 1 Design
**Date**: 2025-05-03

## Overview

This contract defines how the Home Assistant integration calls the `electricityinfo-nz` PyPI library for API access. The wrapper library provides data retrieval, token validation, and error handling.

---

## Library Interface

### Module: `electricityinfo_nz`

The library should provide a main client class for API access.

#### Class: `ElectricityinfoNZ`

**Constructor**:
```python
def __init__(self, access_token: str, timeout: int = 10):
    """
    Initialize Electricityinfo client with OAuth access token.

    Args:
        access_token: Bearer token from OAuth provider
        timeout: Request timeout in seconds (default: 10)

    Raises:
        ValueError: If access_token is empty
    """
```

**Purpose**: Encapsulate token and provide methods for API calls

**Storage**: Token stored in instance (not persisted)

---

### Method: `validate_token()`

**Signature**:
```python
async def validate_token(self) -> bool:
    """
    Validate that the stored token is valid by making a test API call.

    Returns:
        True if token is valid

    Raises:
        AuthenticationError: If token invalid or expired
        ConnectionError: If network error (transient)
        TimeoutError: If request timeout (transient)
    """
```

**Usage in Config Flow**:
```python
async def async_step_auth_validate(self):
    """Validate token before creating config entry."""

    try:
        wrapper = ElectricityinfoNZ(access_token=token)
        await wrapper.validate_token()

        # Token valid, proceed to create config entry
        return self.async_create_entry(
            title="Electricityinfo NZ",
            data={"token": token}
        )

    except AuthenticationError:
        # Token invalid - return to credential input
        return self.async_show_form(
            step_id="user",
            errors={"base": "invalid_token"},
            description_placeholders={
                "help_url": "https://developer.electricityinfo.co.nz"
            }
        )

    except (ConnectionError, TimeoutError):
        # Transient error - show retry button
        return self.async_show_form(
            step_id="auth_validate",
            errors={"base": "cannot_connect"},
            last_step=False
        )
```

**Error Classification**:

| Exception | Meaning | Config Flow Action |
|-----------|---------|-------------------|
| `AuthenticationError` | Token invalid/revoked/expired | Return to Step 1, show help |
| `ConnectionError` | Network error (transient) | Show retry button |
| `TimeoutError` | Request timeout (transient) | Show retry button |
| `Other` | Unexpected error | Show error, allow retry |

---

### Method: `get_data()` (Future)

**Signature** (for Phase 2+ sensor feature):
```python
async def get_data(self) -> dict:
    """
    Retrieve electricity data from API.

    Returns:
        Dictionary containing:
        {
            "prices": [...],
            "generation": {...},
            "demand": {...},
            ...
        }

    Raises:
        AuthenticationError: If token invalid
        APIError: If API error
        ConnectionError: If network error
    """
```

**Note**: Not used by config flow (Phase 1), reserved for sensor feature (Phase 2+)

---

### Exception Hierarchy

**Base**: `Exception`

```
Exception
├── AuthenticationError
│   ├── InvalidToken
│   ├── TokenExpired
│   └── TokenRevoked
│
├── APIError
│   ├── BadRequest
│   ├── ServerError
│   └── RateLimitError
│
├── ConnectionError
│   ├── URLError
│   └── HTTPError
│
└── TimeoutError
```

**Mappings for Config Flow**:
- Any `AuthenticationError` → "Invalid credentials" (permanent failure)
- `ConnectionError` or `TimeoutError` → "Connection error" (transient, allow retry)
- Other exceptions → "Unexpected error" (show help text)

---

## Integration Points

### During Config Flow (Phase 1)

**Step 4: Token Validation**

```python
# Config flow receives OAuth token from Step 3
access_token = oauth_response["access_token"]

# Instantiate wrapper
wrapper = ElectricityinfoNZ(access_token=access_token)

# Validate token
try:
    is_valid = await wrapper.validate_token()

    # Token valid - save config entry
    self.hass.config_entries.async_create_entry(...)

except AuthenticationError:
    # Token invalid - show error
    return self.async_show_form(
        step_id="user",
        errors={"base": "invalid_auth"}
    )
```

### During Integration Setup (Phase 1+)

```python
# In __init__.py async_setup_entry()

async def async_setup_entry(hass, config_entry):
    """Set up Electricityinfo from config entry."""

    # Get token from config entry
    token_data = config_entry.data.get("token")
    access_token = token_data.get("access_token")

    # Create wrapper instance
    wrapper = ElectricityinfoNZ(access_token=access_token)

    # Store wrapper in hass.data for platform setup
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        "wrapper": wrapper,
        "token": token_data
    }

    # Forward setup to platforms (Phase 2+)
    await hass.config_entries.async_forward_entry_setups(
        config_entry,
        PLATFORMS  # ["sensor"]
    )
```

### Future: Sensor Platform (Phase 2+)

```python
# In sensor.py async_setup_entry()

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up sensors from config entry."""

    # Get wrapper from hass.data
    wrapper = hass.data[DOMAIN][config_entry.entry_id]["wrapper"]

    # Create sensor entities
    sensors = [
        ElectricityPriceSensor(wrapper),
        GenerationSensor(wrapper),
        ...
    ]

    async_add_entities(sensors)
```

---

## Error Handling Contract

### Authentication Errors (Permanent Failures)

**Trigger**: Token invalid, expired, or revoked

**Config Flow Behavior**:
1. Catch `AuthenticationError` from `validate_token()`
2. Show error message: "Authentication failed. Please check your credentials."
3. Provide help link: https://developer.electricityinfo.co.nz
4. Return to Step 1 (re-enter credentials)

**Integration Behavior**:
1. Validate token on startup (`async_setup_entry`)
2. If invalid, set `config_entry.async_abort_reload()` with notification
3. Require user to re-authenticate via config flow

### Connection Errors (Transient Failures)

**Trigger**: Network timeout, DNS failure, temporary unavailability

**Config Flow Behavior**:
1. Catch `ConnectionError` or `TimeoutError`
2. Show message: "Could not connect to API. Please try again."
3. Show retry button (preserves state)
4. Allow up to 3 retries before permanent error

**Integration Behavior**:
1. Don't validate token at startup if network down
2. Retry token validation with exponential backoff
3. Don't disable integration (transient)

---

## Token Management Contract

### Token Storage

**Location**: Home Assistant credential storage (encrypted AES-256)

**Format**:
```json
{
  "auth_implementation": "electricityinfo_nz",
  "token": {
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "refresh_...",
    "obtained_at": 1714761123.45
  }
}
```

### Token Refresh

**Responsibility**: Home Assistant handles token refresh automatically

**When**: Before token expiration (60 second buffer)

**How**:
1. Home Assistant detects token near expiration
2. Calls provider's token refresh endpoint
3. Updates `config_entry.data["token"]` automatically
4. Integration reads updated token on next API call

**Wrapper Responsibility**: Accept updated token on next instantiation

```python
# On next API call, wrapper gets fresh token from config entry
new_token = config_entry.data["token"]["access_token"]
wrapper = ElectricityinfoNZ(access_token=new_token)
```

---

## Timeout & Retry Contract

### Request Timeout

**Default**: 10 seconds

**Config**: Settable via `ElectricityinfoNZ(timeout=30)`

**Behavior**: Raise `TimeoutError` if no response within timeout

### Retry Strategy (Config Flow)

```python
# Config flow retry logic
retry_count = 0
max_retries = 3

while retry_count < max_retries:
    try:
        await wrapper.validate_token()
        break  # Success
    except (ConnectionError, TimeoutError) as e:
        retry_count += 1
        if retry_count < max_retries:
            # Show retry button (state preserved)
            return self.async_show_form(...)
        else:
            # Max retries exceeded
            return self.async_show_form(
                errors={"base": "cannot_connect"},
                description_placeholders={
                    "help_url": "https://status.electricityinfo.co.nz"
                }
            )
```

### Retry Strategy (Integration)

```python
# Integration retry logic (on startup validation)
async def async_setup_entry(hass, config_entry):
    """Setup with retry logic."""

    for attempt in range(3):
        try:
            wrapper = ElectricityinfoNZ(access_token=token)
            await wrapper.validate_token()
            break  # Success
        except (ConnectionError, TimeoutError):
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)  # Backoff
            else:
                # Log warning but don't fail
                _LOGGER.warning("Token validation failed after retries")
                break
```

---

## Logging & Security Contract

### What to Log

✅ **OK to log**:
- Token validation attempt (no token value)
- Success/failure result
- Error type (without details)
- Timing information
- Configuration entry ID

### What NOT to Log

❌ **NEVER log**:
- Full access token
- Client ID
- Client secret
- OAuth callback URLs with code
- Raw API responses with sensitive data
- Error messages containing token details

### Logging Examples

```python
# ✅ GOOD
_LOGGER.debug("Validating token for entry %s", config_entry.entry_id)
_LOGGER.info("Token validation successful for %s", config_entry.title)

# ❌ BAD
_LOGGER.debug("Token: %s", access_token)  # Never!
_LOGGER.error("Failed: %s", str(error))   # May contain secrets
_LOGGER.debug("Response: %s", response)   # May contain secrets
```

---

## Backward Compatibility

### Version 1.0 (Initial Release)

- Supports only OAuth 2.0 bearer tokens
- Single token instance per config entry
- No token refresh handling (Home Assistant manages)
- No rate limiting handling

### Future Versions

- Support for refresh_token (if provider adds)
- Multi-region support
- Caching layer
- Rate limit backoff

**Breaking Changes Tracked**: OAuth scope changes = MAJOR version bump

---

## Summary Table

| Aspect | Requirement | Phase |
|--------|-------------|-------|
| Constructor | Accept access_token | 1 |
| validate_token() | Make test API call | 1 |
| Exception hierarchy | AuthenticationError, ConnectionError, TimeoutError | 1 |
| Error classification | Permanent vs. transient | 1 |
| Token storage | Home Assistant credential storage (encrypted) | 1 |
| Token refresh | Automatic via Home Assistant | 1 |
| Logging | No secrets logged | 1 |
| Timeout handling | Default 10s, raise TimeoutError | 1 |
| get_data() | (Reserved for Phase 2 sensors) | 2+ |
