# Feature Specification: OAuth Config Flow Authentication

**Feature Branch**: `001-oauth-config-flow`
**Created**: 2026-05-03
**Status**: Draft
**Input**: Config Flow with OAuth Authentication for Home Assistant integration with PyPI library API wrapper

## Clarifications

### Session 2026-05-03

- Q1: Token Refresh Strategy → A: Automatic refresh (integration handles token refresh transparently before expiration via PyPI wrapper)
- Q2: Config Flow Error Recovery → A: Resume from checkpoint (store OAuth state; users can retry after fixing problem via Home Assistant state checkpointing)
- Q3: Multiple Integration Instances → A: One instance only (single OAuth token; simpler design; multiple instances can be added in future feature)
- Q4: Token Storage & Credential Sourcing → Custom: User-provided credentials via config flow, encrypted and stored in Home Assistant device database. Users sign up at https://developer.electricityinfo.co.nz to obtain client_id and client_secret
- Q5: Config Flow Presentation & Guidance → A: Detailed guidance (include help text, links to developer portal, instructions, validation hints for better first-time user experience)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initial OAuth Setup (Priority: P1)

A new user installs the Electricityinfo NZ integration from HACS and needs to authenticate with their electricity provider's OAuth service to authorize data access.

**Why this priority**: Without OAuth setup, the integration cannot fetch any data. This is the critical path for every new user.

**Independent Test**: Can be fully tested by installing integration, starting config flow, completing OAuth authorization, and verifying Home Assistant stores encrypted token.

**Acceptance Scenarios**:

1. **Given** user navigates to Settings → Devices & Services → Create Integration, **When** user selects "Electricityinfo NZ", **Then** config flow starts with OAuth authentication prompt
2. **Given** user in OAuth prompt, **When** clicking "Authenticate", **Then** user is redirected to OAuth provider's authorization page
3. **Given** user authorizes on OAuth provider, **When** OAuth provider redirects back to Home Assistant, **Then** config flow receives and validates access token
4. **Given** valid OAuth token received, **When** config flow saves configuration, **Then** token is stored encrypted in Home Assistant and visible in Integrations list

---

### User Story 2 - Token Validation (Priority: P1)

The config flow validates that the obtained OAuth access token actually works by testing connectivity to the electricity data API before saving configuration.

**Why this priority**: Invalid tokens will cause the integration to fail silently after setup. Early validation prevents user confusion and support requests.

**Independent Test**: Can be fully tested by submitting an invalid/expired token and verifying error message + re-auth prompt.

**Acceptance Scenarios**:

1. **Given** OAuth token obtained, **When** config flow attempts to validate token with PyPI wrapper, **Then** successful response indicates valid token
2. **Given** invalid or expired token, **When** config flow validates, **Then** error message displays ("Token invalid or expired") and user is prompted to re-authenticate
3. **Given** network error during validation, **When** config flow cannot reach API, **Then** user sees helpful error ("Cannot verify token - check internet connection") with option to retry

---

### User Story 3 - Token Expiration & Re-Authentication (Priority: P2)

When a stored OAuth token expires or becomes invalid, the user can refresh authentication through the integration's config entry options.

**Why this priority**: Tokens can expire over time. Users need a way to refresh without removing and re-adding the integration.

**Independent Test**: Can be fully tested by simulating an expired token scenario and verifying re-auth flow works without data loss.

**Acceptance Scenarios**:

1. **Given** integration with expired token, **When** user opens config entry options, **Then** "Re-authenticate" button is visible
2. **Given** user clicks "Re-authenticate", **When** OAuth flow completes with valid token, **Then** token is updated and integration continues working
3. **Given** during re-auth, **When** new authorization succeeds, **Then** previous configuration (sensor settings, intervals) is preserved

---

### User Story 4 - Config Entry Management (Priority: P3)

A user can view, edit, or remove a configured Electricityinfo NZ integration entry.

**Why this priority**: Standard Home Assistant integration lifecycle. Lower priority as it doesn't affect core auth functionality.

**Independent Test**: Can be fully tested by creating entry, viewing it in integrations list, removing it, and verifying cleanup.

**Acceptance Scenarios**:

1. **Given** configured integration entry, **When** user views Integrations list, **Then** "Electricityinfo NZ" shows as an available entry with status
2. **Given** user viewing integration entry, **When** clicking "Delete", **Then** integration is removed and no longer fetches data
3. **Given** removed integration, **When** user checks Home Assistant config, **Then** no residual config or credentials remain

---

## Functional Requirements

### FR-001: OAuth Flow Implementation
The integration MUST implement OAuth 2.0 authorization code flow using client_id and client_secret provided by the user during config flow setup. Users MUST sign up at https://developer.electricityinfo.co.nz, create an application, and obtain their OAuth credentials. The config flow MUST provide detailed guidance including help text, links to the developer portal, step-by-step instructions for obtaining credentials, and field validation hints. The config flow must guide users through the authorization process without requiring manual token entry.

**Clarification**: Client credentials are user-provided via config flow with detailed guidance. Users register at https://developer.electricityinfo.co.nz first. Config flow includes helpful links and instructions for first-time users.

**Assumptions**: OAuth provider supports standard authorization code flow; Home Assistant provides OAuth helper utilities; developer portal is stable and documented.

### FR-002: Credential Encryption & Storage
OAuth access tokens MUST be stored encrypted using Home Assistant's credential storage system. Client credentials (client_id, client_secret) collected from users via config flow MUST also be stored encrypted in Home Assistant's device database. Tokens and credentials MUST NEVER appear in logs, debug output, or error messages. The PyPI wrapper uses stored credentials to obtain and manage access tokens.

**Assumptions**: Home Assistant credential encryption is enabled by default; tokens and credentials are read-only after setup.

### FR-003: Token Validation
Before saving configuration, the config flow MUST validate the obtained OAuth token by calling the PyPI library wrapper to verify token validity. If validation fails, an error message MUST display and user prompted to re-authenticate.

**Assumptions**: PyPI wrapper provides a simple token validation method; validation completes within 5 seconds.

### FR-004: Token Expiration Handling
The integration MUST detect expired or invalid tokens and provide a simple re-authentication flow via config entry options. Token refresh MUST NOT disrupt existing configuration or sensor setup. The PyPI wrapper MUST automatically refresh tokens transparently before expiration, preventing user-facing authentication failures during normal operation.

**Clarification**: Automatic token refresh strategy used. Integration delegates refresh logic to PyPI wrapper; users only see re-auth prompt if provider revokes token or refresh fails.

**Assumptions**: PyPI wrapper handles token expiration detection and automatic refresh; Home Assistant supports re-auth flows.

### FR-005: Config Entry Display
A successfully configured integration MUST appear in the Home Assistant Integrations UI with status and re-authentication controls. Only ONE instance of the integration may be configured per Home Assistant installation. Any attempt to add a second instance MUST be rejected with an informative error message directing the user to reconfigure the existing entry.

**Clarification**: Single instance constraint enforced. Simplifies token management and sensor configuration; multiple instances can be supported in future feature if needed.

**Assumptions**: Follows standard Home Assistant entity/platform naming conventions.

### FR-006: Error Handling & User Messaging
All error states (network failure, invalid token, provider unavailable) MUST display user-friendly messages with actionable next steps. Technical error details MUST be logged but not shown to users. Config flow MUST support state checkpointing to allow users to resume authentication after network errors or transient failures without restarting the entire flow.

**Clarification**: Resume-from-checkpoint strategy used. Integration stores OAuth state using Home Assistant's config flow framework; users can retry after resolving network issues.

**Assumptions**: User can understand generic terms like "token expired" and "try again".

---

## Success Criteria

- **User Onboarding**: New users can complete OAuth authentication and enable the integration in under 5 minutes
- **Token Validation**: 100% of invalid tokens are caught before configuration is saved, preventing silent failures
- **Encryption Compliance**: Zero instances of OAuth tokens appearing in logs, errors, or config files (audit via test coverage)
- **Re-Authentication**: Users can refresh expired tokens without losing existing configuration or data
- **Test Coverage**: Config flow code achieves >80% test coverage with integration tests for all happy and error paths
- **Home Assistant Integration**: Integration entry appears correctly formatted in Home Assistant UI with working controls

---

## Key Entities

**OAuth Token**:
- Attribute: `access_token` (encrypted string)
- Attribute: `token_type` (typically "Bearer")
- Attribute: `expires_in` (optional, seconds until expiration)
- Attribute: `refresh_token` (if provider supports refresh)
- Usage: Passed to PyPI wrapper for all API calls

**Config Entry**:
- Attribute: `entry_id` (unique identifier)
- Attribute: `title` (display name, e.g., "Electricityinfo NZ")
- Attribute: `data` (contains encrypted token via Home Assistant)
- Attribute: `options` (user-configurable later, e.g., update frequency)

---

## Scope & Constraints

**In Scope**:
- OAuth 2.0 authorization code flow implementation with user-provided credentials
- Config flow UI for credential collection with detailed guidance and links
- Token validation before saving
- Re-authentication flow for expired tokens
- Automatic token refresh via PyPI wrapper
- State checkpointing for error recovery
- Encrypted credential storage (client_id, client_secret, access token)
- Single instance enforcement

**Out of Scope**:
- Sensor platform implementation (separate feature)
- Data fetching or caching logic
- Sensor configuration options (handled in later feature)
- Home Assistant authentication/account setup
- Multiple concurrent integrations per installation

**Constraints**:
- Must use Home Assistant config flow framework (async/await)
- Client credentials collected from users (not hardcoded)
- Tokens MUST be encrypted; no plaintext storage
- Integration must validate token before user can save configuration
- Only one config entry allowed per Home Assistant instance
- Config flow must include links to https://developer.electricityinfo.co.nz

---

## Assumptions

1. PyPI library wrapper provides a working OAuth client and token validation method
2. Electricity provider OAuth service is publicly documented and stable
3. Home Assistant credential encryption is available and enabled
4. Users have stable internet connection for OAuth redirect flow
5. OAuth provider callback URL is `<home-assistant-url>/auth/external/callback` (standard Home Assistant pattern)
6. Client ID and secret are provisioned separately (not part of this feature)

---

## Testing Notes

- Unit tests use mocked OAuth responses and Home Assistant test utilities
- Integration tests verify config flow lifecycle with real Home Assistant test instance
- Error cases include: invalid token, expired token, network failure, provider unavailable
- All tests use fixture credentials; no real API calls in test suite

---

## Dependencies

**Depends on**:
- Constitution: OAuth principle (II. OAuth Token-Based Authentication)
- Constitution: Test-First principle (IV. Test-First Methodology)
- External: PyPI electricity data library with OAuth support

**Enables**:
- Sensor platform feature (cannot exist without working OAuth)
- Configuration & sensor customization features (depend on auth working)
