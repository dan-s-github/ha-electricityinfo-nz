# Data Model: OAuth Config Flow

**Phase**: Phase 1 Design
**Date**: 2025-05-03
**Input**: research.md + Feature Spec

## Entity Definitions

### OAuth Token Entity

**Storage**: Home Assistant credential storage (encrypted AES-256)
**Lifecycle**: Created during config flow validation, refreshed automatically by Home Assistant

```python
@dataclass
class OAuthToken:
    """OAuth 2.0 access token for Electricityinfo API."""

    access_token: str          # Bearer token for API requests
    token_type: str = "Bearer" # OAuth token type
    expires_in: int = 3600     # Seconds until expiration
    refresh_token: str | None = None  # For manual refresh if needed
    obtained_at: float = None  # Unix timestamp (auto-set)

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        if not self.obtained_at:
            return False
        elapsed = time.time() - self.obtained_at
        return elapsed > (self.expires_in - 60)  # Refresh 60s before expiry
```

**Validation Rules**:
- `access_token` must be non-empty string
- `token_type` must be "Bearer"
- `expires_in` must be positive integer (minimum 300 seconds)
- `obtained_at` must be set at token creation (immutable)

**Storage Format** (in Home Assistant config entry):

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

---

### Config Entry Entity

**Storage**: Home Assistant config entry database
**Lifecycle**: Created after OAuth validation, single instance per installation

```python
@dataclass
class ConfigEntry:
    """Home Assistant integration configuration entry."""

    entry_id: str                    # UUID, auto-generated
    title: str = "Electricityinfo NZ"
    version: int = 1
    unique_id: str = "electricityinfo_nz"  # Single instance enforcement
    data: dict = None                # Contains encrypted token
    options: dict = None             # Reserved for sensor settings (future feature)
    state: str = "loaded"            # loaded | not_loaded
    disabled_by: str | None = None   # User | Restart | None

    # Metadata
    created_at: float = None         # Unix timestamp
    updated_at: float = None         # Unix timestamp
```

**Validation Rules**:
- `unique_id` must be "electricityinfo_nz" (single instance constraint)
- `entry_id` must be unique UUID
- `data.token` must contain valid OAuthToken

**Relationships**:
- Config Entry 1:1 → OAuthToken (stored in `data` field)
- Config Entry 1:∞ → Sensor entities (future feature)

**State Transitions**:

```
┌─────────────┐
│  Not Exists │
└──────┬──────┘
       │ User creates config flow
       ↓
┌──────────────────────┐
│  Validating Token    │
├──────────────────────┤
│ - OAuth code exchange│
│ - Token validation   │
│ - Credential storage │
└──────┬───────────────┘
       │ Success
       ↓
┌──────────────────────┐
│  Entry Loaded        │
├──────────────────────┤
│ - Token stored       │
│ - Ready for sensors  │
└──────┬───────────────┘
       │ User disables
       ↓
┌──────────────────────┐
│  Entry Disabled      │
└──────────────────────┘
```

---

### Config Flow State Entity

**Storage**: Temporary (in-memory during config flow, cleared after completion)
**Lifecycle**: Created at config flow start, cleared at completion or cancellation

```python
@dataclass
class ConfigFlowState:
    """Intermediate state during OAuth authorization flow."""

    # User-provided credentials
    client_id: str                   # OAuth client ID
    client_secret: str               # OAuth client secret (never logged)

    # OAuth state management
    oauth_state: str                 # CSRF token (random 32-char string)
    oauth_code: str | None = None    # Authorization code from provider
    redirect_uri: str = "https://your-ha-domain/auth/authorize_callback"

    # Checkpointing for error recovery
    current_step: str = "user"       # user | auth | auth_validate
    error_message: str | None = None # User-friendly error text
    retry_count: int = 0             # For transient error handling
```

**Validation Rules**:
- `client_id` must be non-empty, printable string
- `client_secret` must be non-empty; never logged or displayed
- `oauth_state` must be cryptographically random (32+ characters)
- `redirect_uri` must match Home Assistant OAuth callback URL

**State Checkpointing**:

```python
# Save state to allow retry on error
state_checkpoint = {
    "client_id": "user-provided-id",
    "current_step": "auth",
    "oauth_state": "random-csrf-token",
    "retry_count": 1
}

# On transient error, return form with existing state preserved
# User can retry without re-entering credentials
```

---

## Relationships & Dependencies

### Relationship Diagram

```
┌─────────────────────┐
│  Config Entry       │
├─────────────────────┤
│ - entry_id          │
│ - unique_id         │  1:1
│ - data (token)      │────────┬──────────────────┐
│ - options           │        │                  │
└─────────────────────┘        ↓                  ↓
                        ┌──────────────┐  ┌──────────────┐
                        │ OAuth Token  │  │ Config Flow  │
                        ├──────────────┤  │ State        │
                        │ access_token │  ├──────────────┤
                        │ expires_in   │  │ client_id    │
                        │ refresh_token│  │ oauth_state  │
                        └──────────────┘  │ current_step │
                                          └──────────────┘

Future relationship (Phase 2+):

┌─────────────────────┐
│  Config Entry       │
└──────────┬──────────┘
           │ 1:∞ (contains)
           ↓
      ┌────────────────┐
      │ Sensor Entries │
      ├────────────────┤
      │ - entity_id    │
      │ - name         │
      │ - state        │
      │ - attributes   │
      └────────────────┘
```

---

## Lifecycle State Machines

### Config Entry Lifecycle

```yaml
States:
  - "loaded"           # Entry loaded, sensors available
  - "not_loaded"       # Entry exists but not active
  - "migration"        # Version migration in progress

Transitions:
  loaded + restart → not_loaded → loaded
  loaded + disable → not_loaded
  not_loaded + enable → loaded
  * + remove → (deleted)
  * + error → loaded (recovery)
```

### OAuth Token Lifecycle

```yaml
States:
  - "valid"            # Token usable, not expired
  - "expiring"         # Within 60 seconds of expiration
  - "expired"          # Past expiration time
  - "refreshing"       # Refresh in progress
  - "invalid"          # Validation failed (permanent)

Transitions:
  valid + time_passes → expiring → expired
  valid + validation_fail → invalid
  expired + refresh_success → valid
  expired + refresh_fail → invalid
  invalid + reauth → valid (via config flow)
```

### Config Flow State Machine

```yaml
States:
  - "user"             # Step 1: Enter credentials
  - "auth"             # Step 2: OAuth redirect
  - "auth_callback"    # Step 3: Handle callback
  - "auth_validate"    # Step 4: Validate token
  - "create_entry"     # Success: Create config entry
  - "error"            # Error: Show error + offer retry
  - "abort"            # Aborted: User cancelled

Transitions:
  user + valid_creds → auth
  auth + oauth_redirect → auth_callback
  auth_callback + code_received → auth_validate
  auth_validate + valid_token → create_entry
  * + transient_error → error (show retry button)
  * + permanent_error → abort (show help text)
  * + user_cancel → abort
```

---

## Data Consistency Rules

### Invariants (must always be true)

1. **Single Instance Constraint**
   - At most one config entry with `unique_id = "electricityinfo_nz"`
   - Enforced: Home Assistant's ConfigFlow framework

2. **Token Encryption**
   - All tokens in database must be encrypted (AES-256)
   - Plaintext tokens never logged or displayed
   - Enforced: Home Assistant credential storage

3. **Token Validity**
   - Stored token must validate against electricityinfo-nz API
   - Checked: During config flow creation
   - Checked: On Home Assistant startup (for existing entries)

4. **State Preservation**
   - Config flow state preserved across retry attempts
   - Lost: Only on user cancel or successful completion
   - Enforced: Home Assistant form helpers

### Cascade Operations

**Delete Config Entry**:
- Removes config entry
- Deletes stored token (automatic via Home Assistant)
- Removes any sensor entities (automatic via Home Assistant)
- Future: Unload any background tasks

**Update Token**:
- Updates `data.token` in config entry
- Refreshes expiration timestamp
- Validates new token before saving
- Triggers sensor refresh if applicable

---

## Validation & Error Handling

### Token Validation Flow

```python
def validate_token(token: OAuthToken) -> bool:
    """Validate OAuth token against API."""
    try:
        # Make test API call
        wrapper = ElectricityinfoNZ(access_token=token.access_token)
        wrapper.validate_token()  # Throws if invalid
        return True
    except AuthenticationError:
        # Token invalid or revoked
        return False
    except ConnectionError:
        # Network error (transient)
        raise  # Re-raise for retry handling
    except TimeoutError:
        # Provider timeout (transient)
        raise  # Re-raise for retry handling
```

### Error Messages (User-Facing)

| Error | Message | Action |
|-------|---------|--------|
| Invalid client_id | "Credentials invalid. Verify at https://developer.electricityinfo.co.nz" | Show help text + retry |
| Network timeout | "Connection timeout. Please try again." | Retry button (state preserved) |
| OAuth provider error | "Authorization failed. Please try again." | Retry button (state preserved) |
| Token expired | "Your token expired. Please re-authenticate." | Re-run config flow |
| Permanent revocation | "Your authorization was revoked. Please re-authenticate." | Re-run config flow |

---

## Next: Phase 1 Contracts

See `contracts/config-flow.md` and `contracts/wrapper-integration.md` for interface specifications.
