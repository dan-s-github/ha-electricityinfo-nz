# Implementation Tasks: OAuth Config Flow Authentication

**Feature**: OAuth Config Flow Authentication for Home Assistant Electricityinfo NZ Integration
**Branch**: `001-oauth-config-flow`
**User Stories**: 4 (P1: 2, P2: 1, P3: 1)
**Total Tasks**: 32
**Estimated Duration**: 3-5 days for core implementation (P1), 1-2 days each for P2/P3

---

## Overview & Strategy

### Implementation Strategy

**MVP Scope**: User Stories 1 & 2 (P1 features)
- OAuth setup and token validation
- Core functionality for every user
- ~18 core tasks
- Estimated 3-4 days

**Full Scope**: All 4 user stories (P1, P2, P3)
- Add re-authentication, config entry management
- ~32 tasks total
- Estimated 5-6 days

**Independent Testing**: Each user story can be tested independently
- US1: OAuth flow works, token stored
- US2: Token validation prevents invalid credentials
- US3: Re-auth updates token without losing config
- US4: Config entry lifecycle (view, edit, remove)

### Dependency Graph

```
US1 (OAuth Setup)
    ↓ (dependency)
US2 (Token Validation)
    ↓ (dependency)
US3 (Re-Authentication)
    ↓ (dependency)
US4 (Config Management)
```

**Note**: Each story depends on completing prior stories (waterfall-style for integrations)

### Parallel Opportunities

Within each user story, these tasks can run in parallel [P] marker):
- **US1**: Can write tests, config flow, constants in parallel after setup
- **US2**: Wrapper integration testing can run while validation logic built
- **US3**: Can implement re-auth UI while token refresh logic developed
- **US4**: Entry deletion, viewing can be implemented in parallel

---

## Phase 1: Project Setup

### Project Initialization & Dependencies

- [X] T001 Create integration entry point (`custom_components/electricityinfo_nz/__init__.py`) with async_setup_entry placeholder and logging setup
- [X] T002 Create config flow module (`custom_components/electricityinfo_nz/config_flow.py`) with ConfigFlow class stub
- [X] T003 [P] Create constants module (`custom_components/electricityinfo_nz/const.py`) with DOMAIN, VERSION, OAuth URLs, strings
- [X] T004 [P] Create strings file (`custom_components/electricityinfo_nz/strings.json`) with user-facing text (config flow, errors, help)
- [X] T005 [P] Create manifest file (`custom_components/electricityinfo_nz/manifest.json`) with version, requirements, codeowners, dependencies
- [X] T006 [P] Create test fixtures (`tests/conftest.py`) with Home Assistant hass fixture, mocked OAuth session, mocked wrapper

### Test Infrastructure Setup

- [X] T007 Create test config flow module (`tests/test_config_flow.py`) with imports, fixtures, test class stub
- [X] T008 Create test init module (`tests/test_init.py`) with setup_entry tests stub
- [X] T009 [P] Create OAuth tests module (`tests/test_oauth.py`) with token validation tests stub
- [X] T010 [P] Create pytest configuration validation (ensure pytest-homeassistant-custom-component installed, asyncio_mode set)

---

## Phase 2: Foundational Requirements

### OAuth Infrastructure & Constants

- [X] T011 Define OAuth URLs in const.py (provider authorize URL, token URL, redirect URI format)
- [X] T012 [P] Define DOMAIN, VERSION, PLATFORMS constants in const.py
- [X] T013 [P] Create integration manifest with OAuth scopes and version
- [X] T014 Implement async config flow scaffolding in config_flow.py with all step methods stubbed

### PyPI Wrapper Integration Foundation

- [X] T015 Add electricityinfo-nz import and initialize wrapper class in config_flow
- [X] T016 [P] Implement async error handling patterns for transient vs permanent failures
- [X] T017 [P] Create wrapper validation method that calls library's validate_token() with proper error classification

---

## Phase 3: User Story 1 - Initial OAuth Setup (P1)

**Goal**: Users can authenticate via OAuth provider and Home Assistant stores encrypted token

**Independent Test Criteria**:
- Config flow starts when user selects integration
- User redirected to OAuth provider
- Callback received and code exchanged for token
- Token stored encrypted in Home Assistant
- Integration shows as "Electricityinfo NZ" in Integrations list

### Step 1: Credential Input (User provides client_id & client_secret)

- [X] T018 [US1] Implement async_step_user() for credential input form (client_id, client_secret fields) in config_flow.py
- [X] T019 [US1] Add client_id/client_secret validation (non-empty check)
- [X] T020 [US1] Add help text and developer portal link (https://developer.electricityinfo.co.nz) to Step 1 form

### Step 2: Token Exchange & Validation

- [X] T021 [US1] [P] Implement async_step_auth_validate() to exchange credentials for access token using library's OAuth2ClientCredentials
- [X] T022 [US1] [P] Capture access_token from oauth.get_token() call
- [X] T023 [US1] Call MarketPricesClient with access_token to validate credentials work
- [X] T024 [US1] [P] Handle authentication errors (invalid credentials) → return to step 1 with help text
- [X] T025 [US1] [P] Handle transient errors (connection, timeout) → show retry button, preserve credentials

### Integration Setup Completion

- [X] T026 [US1] [P] Implement async_setup_entry() in __init__.py to store credentials in hass.data
- [X] T027 [US1] [P] Implement config entry title ("Electricityinfo NZ") and unique_id enforcement (single instance)

### Tests for US1

- [X] T028 [US1] Write test_user_form_valid() — user enters valid credentials, proceeds to token exchange
- [X] T029 [US1] Write test_user_form_invalid_client_id() — empty client_id shows error
- [X] T030 [US1] [P] Write test_token_exchange_success() — credentials exchanged for token successfully
- [X] T031 [US1] [P] Write test_token_validation_success() — valid token creates config entry
- [X] T032 [US1] Write test_config_entry_created() — config entry has correct title and unique_id

---

## Phase 4: User Story 2 - Token Validation (P1)

**Goal**: Config flow validates tokens before saving; invalid credentials show helpful error messages

**Independent Test Criteria**:
- Invalid token shows error with help text
- Network errors allow retry with state preserved
- Validation prevents corrupted config entries
- Users guided to https://developer.electricityinfo.co.nz for help

### Token Validation Implementation

- [X] T033 [US2] Implement transient error handling (ConnectionError, TimeoutError) → show retry button, preserve credentials
- [X] T034 [US2] [P] Implement AuthenticationError handling (token invalid) → return to step 1 with help text
- [X] T035 [US2] [P] Add user-friendly error messages to strings.json ("Invalid auth", "Cannot connect", "Try again")

### Error Recovery Flow

- [X] T036 [US2] [P] Implement retry logic in async_step_auth_validate() for transient errors (max 3 attempts)
- [X] T037 [US2] Implement error message with link to developer portal when token invalid
- [X] T038 [US2] [P] Add attempt counter to track retries and allow user to abort

### Tests for US2

- [X] T039 [US2] Write test_token_validation_invalid() — invalid token shows error message
- [X] T040 [US2] Write test_token_validation_connection_error() — network error shows retry button
- [X] T041 [US2] [P] Write test_token_validation_timeout() — timeout shows retry, allows 3 attempts
- [X] T042 [US2] Write test_error_message_has_help_link() — error includes developer portal URL
- [X] T043 [US2] [P] Write test_credentials_preserved_on_retry() — credentials not lost on retry

---

## Phase 5: User Story 3 - Token Expiration & Re-Authentication (P2)

**Goal**: Users can refresh expired tokens without removing integration

**Independent Test Criteria**:
- Re-authenticate button visible in config entry options
- Re-auth flow updates token in place
- Sensor configuration preserved across re-auth
- Expired token triggers re-auth prompt

### Re-Authentication UI

- [X] T055 [US3] Implement async_step_reauth() to start re-auth flow from options menu
- [X] T055a [US3] [P] Create re-authenticate action in ConfigFlow (async_reauth_handler)
- [X] T056 [US3] [P] Add Re-authenticate button/option to config entry in manifest

### Re-Authentication Flow

- [X] T057 [US3] Implement re-auth as abbreviated OAuth flow (skip credential input if stored, go straight to redirect)
- [X] T058 [US3] [P] Use existing client_id/client_secret from config entry if available
- [X] T059 [US3] On successful re-auth, update config entry token without losing options
- [X] T060 [US3] [P] Preserve sensor configuration and intervals across re-auth

### Token Refresh & Expiration Handling

- [X] T061 [US3] [P] Implement token expiration check (obtained_at + expires_in vs current time)
- [X] T062 [US3] [P] On startup, validate stored token; if expired, trigger re-auth notification
- [X] T063 [US3] Add refresh_token support if provider supplies it (store in data, use for automatic refresh)

### Tests for US3

- [X] T064 [US3] Write test_reauth_flow_triggered() — config entry options show re-auth button
- [X] T065 [US3] [P] Write test_reauth_updates_token() — new token replaces old token
- [X] T066 [US3] [P] Write test_reauth_preserves_options() — sensor config not lost after re-auth
- [X] T067 [US3] Write test_expired_token_detected() — startup checks expiration and prompts re-auth

---

## Phase 6: User Story 4 - Config Entry Management (P3)

**Goal**: Users can view, edit, and remove configured integration entries

**Independent Test Criteria**:
- Config entry visible in Integrations list
- Removing entry cleans up all residual config
- Entry can be disabled/enabled by user

### Config Entry Lifecycle

- [X] T068 [US4] Implement async_unload_entry() in __init__.py to properly unload integration
- [X] T069 [US4] [P] Clean up hass.data entries when unloading
- [X] T070 [US4] [P] Implement async_remove_entry() to delete credentials from Home Assistant storage

### Config Entry Display & Management

- [X] T071 [US4] Verify config entry shows correct title in Integrations list
- [X] T072 [US4] [P] Implement async_update_entry() to support editing options (if needed for future sensors)
- [X] T073 [US4] [P] Add entry.state tracking (loaded, not_loaded, error states)

### Tests for US4

- [X] T074 [US4] Write test_config_entry_shown_in_list() — entry visible in Integrations
- [X] T075 [US4] Write test_config_entry_remove_cleanup() — removing entry cleans all config
- [X] T076 [US4] [P] Write test_config_entry_disable() — user can disable/enable entry
- [X] T077 [US4] [P] Write test_config_entry_reload() — integration reloads without error

---

## Phase 7: Cross-Cutting Concerns & Polish

### Security & Logging

- [X] T078 Add security audit: verify no tokens logged in debug output
- [X] T079 [P] Verify client_secret never stored in plaintext
- [X] T080 [P] Audit error messages: no token details leaked to users
- [X] T081 [P] Add HTTPS enforcement for OAuth redirects

### Documentation & User Guidance

- [X] T082 Update README.md with installation and first-time setup instructions
- [X] T083 [P] Add docstrings to all public methods in config_flow.py and __init__.py
- [X] T084 [P] Create troubleshooting guide: common OAuth errors and solutions
- [X] T085 [P] Add inline comments for complex OAuth logic (CSRF validation, state checkpointing)

### Code Quality

- [X] T086 Run ruff linter: `ruff check --fix custom_components tests`
- [X] T087 Run type checking: `mypy custom_components/electricityinfo_nz`
- [X] T088 [P] Run test coverage: `pytest --cov` and verify >80% coverage
- [X] T089 [P] Run all tests: `pytest tests/` and verify all pass

### Final Integration Testing

- [X] T090 End-to-end test: new install → config flow → token stored → integration ready
- [X] T091 [P] Error scenario test: invalid credentials → helpful error → retry succeeds
- [X] T092 [P] Network resilience test: transient errors → retry logic → eventual success
- [X] T093 [P] Cleanup test: remove integration → no residual config or credentials remain

---

## Task Summary by User Story

| User Story | Priority | Tasks | Est. Time | Tests |
|-----------|----------|-------|-----------|-------|
| US1: OAuth Setup | P1 | T018-T032 (15 core) | 2-3 days | T028-T032 (5 tests) |
| US2: Token Validation | P1 | T033-T038 (6 core) | 1 day | T039-T043 (5 tests) |
| US3: Re-Authentication | P2 | T044-T056 (9 core) | 1-2 days | T057-T060 (4 tests) |
| US4: Config Management | P3 | T061-T070 (10 core) | 1 day | T071-T074 (4 tests) |
| **Polish & QA** | — | T075-T090 (16 cross-cutting) | 1-2 days | — |
| **TOTAL** | — | **56 tasks** | **4-6 days** | **18 tests** |

---

## Recommended Execution Order

### Minimum Viable Product (MVP)

**Scope**: Phases 1-4 (User Stories 1 & 2)
**Duration**: 3-4 days
**Tasks**: T001-T054 (54 tasks)

Delivers core OAuth flow and token validation. Users can authenticate and Home Assistant prevents invalid credentials.

### Phase 1 Extension: P2 Feature

Add User Story 3 (Re-Authentication)
**Duration**: +1-2 days
**Tasks**: T055-T067 (13 tasks)

Adds token refresh capability for long-lived integrations.

### Full Feature

Add User Story 4 (Config Management)
**Duration**: +1 day
**Tasks**: T068-T093 (26 tasks)

Complete integration lifecycle with polish and documentation.

---

## Parallelization Matrix

**Independent Task Groups** (can run simultaneously within phases):

**Phase 1**:
- T003-T006: Constants, strings, manifest, fixtures (parallel)
- T009-T010: OAuth & init tests (parallel)

**Phase 3 (US1)**:
- T021-T023: OAuth state generation (parallel after T020)
- T024-T027: Callback handling (parallel)
- T033-T039: Tests (parallel with implementation T028-T032)

**Phase 4 (US2)**:
- T041-T043: Error handling (parallel)
- T050-T054: Tests (parallel with T040-T049)

**Phase 7 (Polish)**:
- T078-T085: Security & documentation (parallel)
- T086-T089: Code quality checks (parallel)
- T090-T093: Integration tests (parallel)

**Suggested Workflow**:
1. Complete Phase 1 (T001-T010) — 1 day
2. Complete Phase 2 (T011-T017) — 0.5 days
3. **Parallel**: Phase 3 core (T018-T032) + Phase 3 tests (T033-T039) — 2 days
4. **Parallel**: Phase 4 core (T040-T049) + Phase 4 tests (T050-T054) — 1.5 days
5. Phase 5-6 (T055-T077) — 2 days
6. Phase 7 polish (T078-T093) — 1-2 days

**Total**: 5-7 days with parallelization

---

## File Paths Reference

### Source Code Files

```
custom_components/electricityinfo/
├── __init__.py                 # Integration setup (T001)
├── config_flow.py              # OAuth flow (T002, T018-T038)
├── const.py                    # Constants (T003, T011-T013)
├── manifest.json               # Metadata (T005)
└── strings.json                # UI strings (T004)
```

### Test Files

```
tests/
├── conftest.py                 # Fixtures (T006, T010)
├── test_config_flow.py         # Config flow tests (T007, T028-T043)
├── test_init.py                # Setup tests (T008)
└── test_oauth.py               # OAuth tests (T009)
```

### Documentation Files

```
specs/001-oauth-config-flow/    # Design documents (already complete)
README.md                       # Updated with setup (T082)
.github/copilot-instructions.md # Updated with plan reference (already done)
```

---

## Success Criteria

**All User Stories Implemented**: ✅ Each story independently testable
**Test Coverage**: ≥80% code coverage on config flow, init, OAuth logic
**Security**: ✅ No tokens in logs, HTTPS enforced, CSRF protected
**Documentation**: ✅ README updated, docstrings added, troubleshooting guide
**Code Quality**: ✅ Ruff, Mypy, pytest all passing
**Integration Verified**: ✅ End-to-end test with Home Assistant startup

---

## Next Steps After Task Completion

1. **Code Review**: Submit PR to main branch with all tasks completed
2. **HACS Integration**: Add to HACS custom repository
3. **Phase 2 Features**: Start work on sensor platform (future feature)
4. **Community Feedback**: Gather user feedback for refinements

---

**Generated**: 2026-05-03
**Plan Reference**: `specs/001-oauth-config-flow/plan.md`
**Specification Reference**: `specs/001-oauth-config-flow/spec.md`
