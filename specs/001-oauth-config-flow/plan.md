# Implementation Plan: OAuth Config Flow Authentication

**Branch**: `001-oauth-config-flow` | **Date**: 2025-05-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-oauth-config-flow/spec.md`

## Summary

Implement OAuth 2.0 configuration flow for Home Assistant Electricityinfo NZ integration. Users provide client_id/client_secret (obtained from https://developer.electricityinfo.co.nz), config flow handles OAuth redirect authorization, validates tokens via electricityinfo-nz PyPI wrapper, and stores encrypted credentials in Home Assistant. Automatic token refresh via PyPI wrapper prevents user-facing auth failures. Single instance per installation with state checkpointing for error recovery.

## Technical Context

**Language/Version**: Python 3.14+ (Home Assistant requirement)

**Primary Dependencies**:
- `homeassistant==2026.3.1` — Home Assistant integration framework
- `electricityinfo-nz` — PyPI library wrapper for Electricityinfo API
- `pytest>=8.2.0` + `pytest-asyncio>=1.3.0` + `pytest-homeassistant-custom-component==0.13.317` — Async testing

**Storage**: N/A (Home Assistant credential storage handles encryption)

**Testing**: pytest with Home Assistant testing utilities; mocked OAuth responses and PyPI wrapper calls

**Target Platform**: Home Assistant (asyncio-based, Python 3.14+)

**Project Type**: Home Assistant custom integration (config flow + platform)

**Performance Goals**:
- Config flow OAuth flow completes in <5 minutes (user onboarding)
- Token validation completes within 5 seconds
- State checkpointing and error recovery <2 second retry latency

**Constraints**:
- async/await required (Home Assistant framework)
- Zero plaintext tokens in logs/errors
- Client credentials collected from users (not hardcoded)
- Single instance enforcement

**Scale/Scope**: Single integration instance per Home Assistant installation; supports 1 OAuth token; no multi-tenancy

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Library API Wrapper First
- ✅ **PASS**: All API calls route through PyPI wrapper. No direct HTTP code in integration. Config flow validates via wrapper.

### Principle II: OAuth Token-Based Authentication (NON-NEGOTIABLE)
- ✅ **PASS**: OAuth 2.0 bearer token mandatory. User-provided credentials. Encrypted storage via Home Assistant. Tokens never logged. Refresh delegated to wrapper.

### Principle III: Configurable Sensor Architecture
- ✅ **PASS**: This feature enables future sensor configuration. Out of scope for this feature but prerequisite met.

### Principle IV: Test-First Methodology (NON-NEGOTIABLE)
- ✅ **PASS**: TDD enforced. Tests written before implementation. Config flow tests cover happy path + error scenarios. Mocked OAuth + PyPI wrapper.

### Principle V: Semantic Versioning & Breaking Changes
- ✅ **PASS**: Feature is v1.0.0 foundation. Follows semver for future updates. OAuth scope changes tracked as MAJOR.

**Constitution Status**: ✅ **ALL GATES PASS** — Feature aligned with all core principles and security requirements.

## Project Structure

### Documentation (this feature)

```text
specs/001-oauth-config-flow/
├── plan.md              # This file (implementation plan)
├── spec.md              # Feature specification (4 user stories, 6 FRs)
├── research.md          # Phase 0 output (research + technology decisions)
├── data-model.md        # Phase 1 output (data entities, relationships)
├── quickstart.md        # Phase 1 output (developer quickstart)
├── contracts/           # Phase 1 output (config flow + wrapper contracts)
├── checklists/          # Quality validation checklists
└── tasks.md             # Phase 2 output (task list, NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
custom_components/electricityinfo_nz/
├── __init__.py                 # Integration entry point (async_setup_entry)
├── config_flow.py              # Config flow with OAuth implementation
├── const.py                    # Constants (DOMAIN, VERSION, OAuth URLs, etc.)
├── manifest.json               # Integration metadata (version, requirements, codeowners)
├── strings.json                # User-facing strings (config flow labels, error messages)
└── strings/en.json             # English localization

tests/
├── conftest.py                 # pytest fixtures (mock Home Assistant, PyPI wrapper)
├── test_config_flow.py         # Config flow unit tests (auth flow, validation, errors)
├── test_init.py                # Integration lifecycle tests (setup, unload, reload)
└── test_oauth.py               # OAuth token handling tests (validation, expiration)
```

**Structure Decision**: Single Home Assistant integration module with async config flow. Tests organized by component scope (config_flow, init, oauth). Follows Home Assistant custom integration conventions.

## Complexity Tracking

**Status**: No violations. Feature aligns with all constitutional principles. No justification required.

---

## Phase 0: Research & Unknowns

### Research Tasks

1. **electricityinfo-nz PyPI Library OAuth Integration**
   - Task: Analyze electricityinfo-nz library capabilities and OAuth support
   - Questions to resolve:
     - Does library support OAuth 2.0 token refresh automatically?
     - What methods are available for token validation?
     - Does library handle token expiration and error recovery?
   - Output: `wrapper-oauth-api.md` documenting library's OAuth interface

2. **Home Assistant Config Flow OAuth Patterns**
   - Task: Research best practices for OAuth 2.0 in Home Assistant config flows
   - Questions to resolve:
     - How to implement state checkpointing for error recovery?
     - What are Home Assistant's credential encryption mechanisms?
     - Best practices for OAuth redirect URI handling?
   - Output: `config-flow-patterns.md` with code examples and patterns

3. **Home Assistant Testing Patterns for Async Config Flows**
   - Task: Research testing async config flows with mocked external services
   - Questions to resolve:
     - How to mock OAuth provider responses in tests?
     - Best practices for async test fixtures in Home Assistant?
     - Error injection and recovery testing patterns?
   - Output: `testing-patterns.md` with test templates and mocking strategies

### Phase 0 Outcome

**Deliverable**: `research.md` consolidating all research findings with:
- Technology decisions made during research
- Architecture patterns confirmed for OAuth + Home Assistant
- Unknown items resolved and documented
- Rationale for each technology choice

---

## Phase 1: Design & Data Model

### Data Model

**OAuth Token Entity** (encrypted, stored by Home Assistant):
- `access_token` (string): Bearer token for API calls
- `token_type` (string): "Bearer"
- `expires_in` (integer, optional): Seconds until expiration
- `refresh_token` (string, optional): For token refresh (if provider supports)
- `obtained_at` (datetime): Timestamp for expiration calculation

**Config Entry** (Home Assistant integration entry):
- `entry_id` (UUID): Unique identifier
- `title` (string): "Electricityinfo NZ"
- `data` (dict): Encrypted token (managed by Home Assistant)
- `options` (dict): User-configurable (reserved for sensor settings in future feature)
- `unique_id` (string): "electricityinfo_nz" (single instance constraint)

**Config Flow State** (checkpointed during OAuth):
- `client_id` (string): User-provided
- `client_secret` (string): User-provided
- `oauth_state` (string): CSRF token for OAuth flow
- `redirect_uri` (string): Home Assistant callback URL

### Interface Contracts

**Config Flow Contract** (user interaction):
1. Step 1: Credential input (client_id, client_secret)
2. Step 2: OAuth redirect (user authorizes at provider)
3. Step 3: Token validation and storage
4. Result: Config entry saved or error displayed

**PyPI Wrapper Contract** (library integration):
- `wrapper.validate_token(access_token)` → bool (raises exception on error)
- `wrapper.refresh_token(refresh_token)` → {new_token, expires_in}
- `wrapper.get_data(access_token)` → API response (future sensor feature)

### Phase 1 Artifacts to Generate

- **research.md** — Home Assistant config flow patterns, electricityinfo-nz OAuth capabilities, testing strategies
- **data-model.md** — Entity definitions, relationships, lifecycle
- **quickstart.md** — Developer setup guide for working with config flow
- **contracts/config-flow.md** — Config flow UI/UX specification
- **contracts/wrapper-integration.md** — PyPI wrapper interface specification

### Phase 1 Outcome

**Deliverables**:
- ✅ research.md with all technology decisions
- ✅ data-model.md with entity definitions and relationships
- ✅ quickstart.md for developer onboarding
- ✅ contracts/ with interface specifications (config-flow.md, wrapper-integration.md)
- ✅ Copilot context updated with plan reference (`.github/copilot-instructions.md`)

---

## Next Phase

**Phase 2**: `/speckit-tasks` generates implementation task list from design artifacts
- Task decomposition by user story (P1/P1/P2/P3)
- Dependency ordering for parallel work
- Test task generation from acceptance criteria
- Expected output: `tasks.md` with 15-20 tasks organized by story

---

## Notes

- **Pre-commit hook behavior**: Repository has pre-commit hooks that auto-fix trailing whitespace and EOF formatting. Changes made by hooks require re-staging and re-committing. This is expected behavior.

- **Spec-kit sequencing**: Features use sequential numbering (001-oauth-config-flow) independent of git branch names.

- **Constitution-driven**: All design decisions verified against `.specify/memory/constitution.md` before proceeding.
