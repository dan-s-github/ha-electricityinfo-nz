# Config Flow Contract

**Phase**: Phase 1 Design
**Date**: 2025-05-03

## Overview

The config flow is the user-facing interface for OAuth setup. This contract defines the steps, inputs, outputs, and error handling.

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
- Success: Proceed to Step 2 (OAuth redirect)
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
    Label: "Authenticate"
```

**Security**:
- Client secret rendered as password field (hidden)
- Never logged
- Stored in config flow state (in-memory)

---

### Step 2: OAuth Authorization Redirect

**Purpose**: Redirect user to OAuth provider for authorization

**Input**:
- `client_id` (from Step 1)
- `redirect_uri`: https://your-ha-domain/auth/authorize_callback

**Processing**:
1. Generate CSRF token (`oauth_state`) - 32-char random
2. Construct authorization URL: `{provider_url}?client_id={id}&redirect_uri={uri}&state={state}`
3. Return external redirect

**Output**:
- Success: User redirected to provider login
- Error: Show error + option to retry

**External Action**:
```
GET {provider_oauth_authorize_url}
  ?client_id={client_id}
  &redirect_uri=https://{ha_domain}/auth/authorize_callback
  &state={random_csrf_token}
  &response_type=code
```

**Security**:
- CSRF token prevents authorization code interception
- State token validated on callback

---

### Step 3: OAuth Callback Handling

**Purpose**: Receive authorization code from provider and exchange for token

**Input** (from provider callback):
- `code`: Authorization code (valid for ~10 minutes)
- `state`: CSRF token (must match Step 2)

**Processing**:
1. Validate CSRF token matches Step 2
2. Exchange code for token: POST to `{provider_token_url}`
   ```
   POST {provider_token_url}
     client_id={id}
     client_secret={secret}
     code={code}
     grant_type=authorization_code
     redirect_uri={redirect_uri}
   ```
3. Parse response: extract `access_token`, `expires_in`, `refresh_token` (if present)

**Output**:
- Success: Proceed to Step 4 (token validation)
- Code Invalid: Show error "Authorization code invalid or expired"
- CSRF Mismatch: Security error (abort, don't retry)

**Error Handling**:
- Transient errors (timeout, 5xx): Show retry button
- Permanent errors (invalid code, CSRF mismatch): Show help text, link to docs

---

### Step 4: Token Validation

**Purpose**: Verify token works by making test API call

**Input**:
- `access_token` (from Step 3)

**Processing**:
1. Create PyPI wrapper instance with token
2. Make test API call (e.g., get account info or test endpoint)
3. Catch and classify errors:
   - Authentication error: Token invalid
   - Connection error: Transient (allow retry)
   - Timeout: Transient (allow retry)

**Output**:
- Success: Proceed to Step 5 (create config entry)
- Invalid Token: Show error "Token validation failed. Please re-authenticate." (return to Step 1)
- Transient Error: Show retry button (state preserved)

**Validation Details**:
```python
# Test API call structure
wrapper = ElectricityinfoNZ(access_token=token)
wrapper.validate_token()  # Throws AuthenticationError if invalid
```

---

### Step 5: Create Config Entry

**Purpose**: Save configuration and complete setup

**Input**:
- `access_token` (validated from Step 4)
- `token_type`, `expires_in`, etc. (from Step 3)

**Processing**:
1. Home Assistant encrypts token automatically
2. Create config entry:
   ```json
   {
     "title": "Electricityinfo NZ",
     "data": {
       "auth_implementation": "electricityinfo_nz",
       "token": {
         "access_token": "<encrypted>",
         "token_type": "Bearer",
         "expires_in": 3600,
         "obtained_at": 1714761123.45
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
  Description: "Authenticated successfully. Integration ready for sensors."
```

---

## Error Handling & State Recovery

### Transient Error Retry

**Scenario**: Network timeout during Step 3 (code exchange)

**Handling**:
1. Catch timeout exception
2. Show form with error: "Connection timeout. Please try again."
3. Preserve state (client_id, oauth_state)
4. Show retry button (calls same step again)
5. No re-authentication required

**State Preserved**:
```python
self.context["flow_state"] = {
    "client_id": user_input["client_id"],
    "oauth_state": original_state,
    "retry_count": 1
}
```

### Permanent Error Retry

**Scenario**: Invalid client_id / client_secret

**Handling**:
1. Catch AuthenticationError
2. Show form with error + help text
3. Clear sensitive state (oauth_state, code)
4. Return to Step 1 (user re-enters credentials)
5. Link to https://developer.electricityinfo.co.nz for credential help

**Help Text**:
```
Invalid credentials.

Did you:
1. Register at https://developer.electricityinfo.co.nz ?
2. Copy Client ID correctly?
3. Copy Client Secret correctly?

Verify your credentials and try again.
```

### User Cancellation

**Scenario**: User closes OAuth provider window without authorizing

**Handling**:
1. OAuth callback not received
2. After timeout (~5 minutes), offer user:
   - "Try again" → Return to Step 2
   - "Use different credentials" → Return to Step 1
   - "Cancel" → Abort config flow

---

## Security Considerations

### Token Handling

✅ **DO**:
- Store encrypted via Home Assistant credential storage
- Use HTTPS for all OAuth redirects
- Validate CSRF token on callback
- Make test API call to validate token before saving
- Use password input field for client_secret

❌ **DON'T**:
- Log access token or client_secret
- Store credentials in plaintext
- Skip CSRF validation
- Save invalid tokens

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
Step 2: Redirect to OAuth Provider
    ↓
User Authorizes
    ↓
Callback Received
    ↓
┌───────────────────────────────────────────────┐
│ Step 3: Exchange Code for Token              │
└───────────────────────────────────────────────┘
    ↓
    ├─ Timeout/Network Error?
    │     ├─ Yes: Show retry button → Step 3 again
    │     └─ State preserved (oauth_state, code)
    │
    ├─ Invalid Code?
    │     ├─ Yes: Show error "Authorization expired"
    │     └─ Return to Step 1
    │
    └─ CSRF Mismatch?
          ├─ Yes: ABORT (security violation)
          └─ Log incident
    │
    ↓ (Success: code exchanged for token)
    │
┌───────────────────────────────────────────────┐
│ Step 4: Validate Token                       │
└───────────────────────────────────────────────┘
    ↓
    ├─ Invalid Token?
    │     ├─ Yes: Show error + link to help
    │     └─ Return to Step 1
    │
    ├─ Timeout/Network Error?
    │     ├─ Yes: Show retry button → Step 4 again
    │     └─ State preserved (access_token)
    │
    └─ Valid Token?
          ├─ Yes: Continue to Step 5
          └─ No: Abort with error
    │
    ↓
┌───────────────────────────────────────────────┐
│ Step 5: Create Config Entry                  │
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
    #   "token": {
    #     "access_token": "<encrypted>",
    #     "token_type": "Bearer",
    #     "expires_in": 3600,
    #     "obtained_at": 1714761123.45
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
| 2 | ~1s | Click "Authenticate" | Generate redirect URL |
| 3 | ~30s | Authorize in provider | Exchange code for token |
| 4 | ~3s | (automatic) | Validate token with API call |
| 5 | <1s | (automatic) | Save config entry |
| **Total** | **~45s** | | |

**Success**: User sees "Electricityinfo NZ configured successfully"
**Error Recovery**: User retries with state preserved (no loss of progress)
