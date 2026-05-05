# Config Flow Contract

**Phase**: Phase 1 Design
**Date**: 2025-05-03
**Updated**: 2026-05-04

## Overview

The config flow is the user-facing interface for OAuth2 Client Credentials setup. This contract defines the steps, inputs, outputs, and error handling. Unlike Authorization Code flow, Client Credentials eliminates browser redirects and works in offline/local network environments.

---

## Config Flow Steps

### Step 1: User Input (Credentials)

**Purpose**: Collect OAuth credentials from user

**Input**:
- `client_id` (string, required): OAuth client ID from https://developer.electricityinfo.co.nz
- `client_secret` (string, required): OAuth client secret (sensitive field, hidden input)

**Validation**:
- Both fields non-empty
- No whitespace validation (provider may allow spaces)
- No length validation (variable across providers)

**Output**:
- Success: Proceed to Step 2 (token exchange and validation)
- Validation Error: Show form with error message

**UI**:
```yaml
Step: user
Title: "Electricityinfo NZ Setup"
Description: "Enter your OAuth credentials from https://developer.electricityinfo.co.nz"

Fields:
  - Name: client_id
    Type: text
    Label: "Client ID"
    Required: true

  - Name: client_secret
    Type: password
    Label: "Client Secret"
    Required: true
    Description: "Not stored in logs. Safe to enter here."

Buttons:
  - Action: submit
    Label: "Connect"
```

**Security**:
- Client secret rendered as password field (hidden)
- Never logged
- Stored in config flow state (in-memory)

---

### Step 2: Token Exchange & Validation

**Purpose**: Exchange credentials for access token and validate it works

**Input**:
- `client_id` (from Step 1)
- `client_secret` (from Step 1)

**Processing**:
1. Create OAuth2ClientCredentials instance
2. Call get_token() to exchange credentials for access token
3. Create PyPI wrapper instance with token
4. Call get_schedules() to validate token works
5. Catch and classify errors:
   - AuthenticationError: Invalid credentials (permanent)
   - TransportError/TimeoutError: Network issue (transient, allow retry)

**Output**:
- Success: Proceed to Step 3 (create config entry)
- Invalid Credentials: Show error "Invalid client ID or secret" (return to Step 1)
- Network Error: Show retry button (state preserved)

**Token Exchange Details**:
```python
from electricityinfo_nz.auth import OAuth2ClientCredentials
from electricityinfo_nz.client import MarketPricesClient

# Exchange credentials for token
oauth = OAuth2ClientCredentials(
    client_id=client_id,
    client_secret=client_secret,
    base_url="https://api.electricityinfo.co.nz"
)
access_token = oauth.get_token()

# Validate token works
client = MarketPricesClient(access_token=access_token)
schedules = client.get_schedules()  # Throws AuthenticationError if invalid
```

---

### Step 3: Create Config Entry

**Purpose**: Save configuration and complete setup

**Input**:
- `access_token` (validated from Step 2)
- `client_id`, `client_secret` (encrypted)

**Processing**:
1. Home Assistant encrypts credentials automatically
2. Create config entry:
   ```json
   {
     "title": "Electricityinfo NZ",
     "data": {
       "auth_implementation": "electricityinfo_nz",
       "credentials": {
         "client_id": "<encrypted>",
         "client_secret": "<encrypted>"
       }
     }
   }
   ```
3. Entry loaded and ready for sensors

**Output**:
- Success: "Configuration saved!"
- Duplicate: "Electricityinfo NZ already configured"

**UI**:
```yaml
Result:
  Type: create_entry
  Title: "Electricityinfo NZ"
  Description: "Connected successfully. Integration ready for sensors."
```

---

## Error Handling & State Recovery

### Transient Error Retry

**Scenario**: Network timeout during Step 2 (token exchange)

**Handling**:
1. Catch timeout exception
2. Show form with error: "Connection timeout. Please try again."
3. Preserve state (client_id, client_secret)
4. Show retry button (calls same step again)
5. No re-authentication required

**State Preserved**:
```python
self.context["flow_state"] = {
    "client_id": user_input["client_id"],
    "client_secret": user_input["client_secret"],
    "retry_count": 1
}
```

### Permanent Error Retry

**Scenario**: Invalid client_id / client_secret

**Handling**:
1. Catch AuthenticationError
2. Show form with error + help text
3. Return to Step 1 (user re-enters credentials)
4. Link to https://developer.electricityinfo.co.nz for credential help

**Help Text**:
```
Invalid credentials.

Did you:
1. Register at https://developer.electricityinfo.co.nz ?
2. Copy Client ID correctly?
3. Copy Client Secret correctly?

Verify your credentials and try again.
```

---

## Security Considerations

### Token Handling

✅ **DO**:
- Store credentials encrypted via Home Assistant credential storage
- Use HTTPS for all token exchange requests
- Make test API call to validate token before saving
- Use password input field for client_secret

❌ **DON'T**:
- Log access token or client_secret
- Store credentials in plaintext
- Save invalid tokens
- Display raw error details in UI

### Error Messages

✅ **DO**:
- Show user-friendly error text
- Provide actionable next steps
- Link to documentation/help portal
- Preserve state for retry attempts

❌ **DON'T**:
- Display raw error codes or stack traces
- Mention token details in error messages
- Log raw OAuth responses
- Show provider error messages directly

---

## Recovery Flowchart

```
Start Config Flow
    ↓
Step 1: Enter Credentials
    ↓
┌───────────────────────────────────────────────┐
│ Step 2: Exchange Credentials for Token       │
│         & Validate Token Works               │
└───────────────────────────────────────────────┘
    ↓
    ├─ Timeout/Network Error?
    │     ├─ Yes: Show retry button → Step 2 again
    │     └─ State preserved (client_id, client_secret)
    │
    ├─ Invalid Credentials?
    │     ├─ Yes: Show error + help text
    │     └─ Return to Step 1
    │
    └─ Token Valid?
          ├─ Yes: Continue to Step 3
          └─ No: Abort with error
    │
    ↓
┌───────────────────────────────────────────────┐
│ Step 3: Create Config Entry                  │
└───────────────────────────────────────────────┘
    ↓
SUCCESS: "Configuration saved!"
```

---

## Configuration Entry Output

**Format**: Home Assistant `ConfigEntry` object

```python
@dataclass
class ConfigEntry:
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "Electricityinfo NZ"
    version: int = 1
    unique_id: str = "electricityinfo_nz"

    data: dict = Field(default_factory=dict)
    # data contains:
    # {
    #   "auth_implementation": "electricityinfo_nz",
    #   "credentials": {
    #     "client_id": "<encrypted>",
    #     "client_secret": "<encrypted>"
    #   }
    # }

    options: dict = Field(default_factory=dict)
    # Reserved for future sensor configuration
```

---

## User Experience Summary

| Step | Duration | User Action | System Action |
|------|----------|-------------|---------------|
| 1 | <10s | Enter credentials | Collect input |
| 2 | ~2s | (automatic) | Exchange credentials & validate token |
| 3 | <1s | (automatic) | Save config entry |
| **Total** | **~13s** | | |

**Success**: User sees "Electricityinfo NZ configured successfully"
**Error Recovery**: User retries with state preserved (no loss of progress)
**Benefit**: Works in offline/local network environments (no browser redirect required)
