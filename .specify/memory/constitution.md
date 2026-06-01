<!-- SYNC IMPACT REPORT
Version Change: 1.1.0 → 1.2.0 (MINOR - Added Principle VI: Documentation Synchronization; README sync is now mandatory)
Modified Principles: None
Added Sections: VI. Documentation Synchronization (new core principle)
Removed Sections: None
Templates Updated:
  ✅ .specify/memory/constitution.md (this file)
  ✅ Development Workflow: Code Review checklist updated (item f added)
  ✅ .specify/templates/plan-template.md — Principle VI documentation gate added to Constitution Check section
  ✅ .specify/templates/tasks-template.md — "Update README" task added to Phase N with mandatory Principle VI note
Templates Pending: None
Follow-up TODOs: None
-->

# Electricityinfo NZ Constitution

Home Assistant custom integration providing configurable electricity price sensors via PyPI library wrapper with OAuth authentication.

## Core Principles

### I. Library API Wrapper First

Every feature integrating with external APIs MUST use a PyPI library wrapper as the single source of truth. Custom HTTP logic is prohibited; all API communication flows through the wrapper. This ensures contract stability, error consistency, and isolated testing.

**Rationale**: Direct HTTP code in integration logic causes brittleness when APIs change. Wrapping isolation enables parallel library development and Home Assistant integration development. Library must be independently testable and versioned separately.

### II. OAuth Token-Based Authentication (NON-NEGOTIABLE)

All integration connections require OAuth API token authentication. Tokens are obtained through secure config flow, stored encrypted in Home Assistant, and never logged or exposed. Token refresh and expiration handling is mandatory. Hard-coded credentials or deprecated auth methods are prohibited.

**Rationale**: OAuth provides secure delegated access without exposing user credentials. Home Assistant's credential encryption protects sensitive tokens. Token expiration handling prevents authentication failures breaking automations. Config flow validation ensures tokens work before saving.

### III. Configurable Sensor Architecture

All sensors MUST be configurable via the Home Assistant config flow (Config Subentry Flow). Configuration drives sensor instantiation, data collection intervals, and display logic. Hard-coded sensors are prohibited.

**Rationale**: End users have varying electricity data needs. The Config Subentry Flow provides a guided, validated configuration experience without requiring manual YAML editing. Configuration flexibility enables different regions/retailers to use one integration without forking. Config flow MUST validate OAuth token availability at setup time.

### IV. Test-First Methodology (NON-NEGOTIABLE)

TDD is mandatory: test cases written and approved by stakeholders → red failing tests → implementation → green passing tests → refactor. Red-Green-Refactor cycle strictly enforced. Unit tests cover library wrapper usage with mocked OAuth tokens; integration tests cover config flow, OAuth token validation, and sensor platform lifecycle.

**Rationale**: Home Assistant integrations are critical infrastructure; silent failures can break automation. Tests protect against regression and document expected behavior for future maintainers. OAuth flow testing prevents auth failures in production.

### V. Semantic Versioning & Breaking Changes

Version format: MAJOR.MINOR.PATCH. MAJOR increments for breaking changes (config schema changes, sensor removal, OAuth scope changes, library wrapper incompatibility). MINOR for new features (new sensors, new config options). PATCH for fixes (bug fixes, typo fixes, dependency updates).

**Rationale**: Home Assistant users depend on stable schemas. Breaking changes MUST be announced. Library wrapper version constraints enforced in integration requirements. OAuth scope changes require user re-authentication.

### VI. Documentation Synchronization

The `README.md` MUST be kept in sync with the implementation at all times. Any change to user-facing behaviour — new sensors, changed configuration options, updated setup steps, revised entity descriptions, or removed features — MUST be accompanied by a corresponding README update in the same commit or PR. Merging implementation changes without updating the README is prohibited.

**Rationale**: The README is the primary reference for users installing and configuring the integration. Stale documentation causes misconfiguration, support burden, and loss of trust. Treating documentation as a first-class deliverable — not an afterthought — ensures users always have accurate guidance. This applies equally to HACS-published releases and development builds.

## Security & Authentication

**OAuth Requirements**:

- Integration MUST use OAuth 2.0 bearer token authentication with the PyPI library wrapper
- OAuth flow uses `client_id` and `client_secret` to obtain access tokens from provider
- Config flow MUST implement OAuth token validation before saving configuration
- Access tokens MUST be stored encrypted in Home Assistant's credential storage (via `async_setup_platform`)
- Client credentials (`client_id`, `client_secret`) stored securely; never in logs or config files
- Access tokens MUST NOT appear in logs, debug output, or error messages
- Token refresh and expiration handling delegated to PyPI library wrapper
- Config entry options MUST NOT store raw tokens or credentials (Home Assistant handles encryption)

**Credential Management**:

- OAuth access tokens are sensitive secrets and treated as encrypted by default
- Client ID and secret are configured once and used by PyPI wrapper for token acquisition
- Config flow implements OAuth redirect flow for user authorization (never collect raw tokens manually)
- Unit tests use mocked/fixture tokens and credentials; integration tests use test credentials only
- Expired or invalid tokens trigger re-authentication flow in config entry options
- Token revocation or credential rotation requires config entry re-setup

## Technology Stack

**Language**: Python 3.14+
**Framework**: Home Assistant custom integration architecture (async/await, config flow, entity platform)
**API Wrapper**: PyPI-published library wrapper (semantically versioned, OAuth support mandatory)
**Authentication**: OAuth 2.0 with Home Assistant credential encryption
**Testing**: pytest with Home Assistant testing utilities, mocking for OAuth tokens and library calls
**Linting**: Ruff (format + lint)
**CI/CD**: GitHub Actions with tests, linting, and HACS validation gates

**Core Dependencies**:

- `homeassistant` (Home Assistant core API)
- PyPI library wrapper with OAuth support (pinned to compatible MAJOR version)
- pytest (testing)
- pytest-asyncio (async test support)

**Constraints**: Library wrapper MUST provide OAuth token handling; no manual token refresh in integration code. Library wrapper MUST NOT have unmanaged external HTTP dependencies.

## Development Workflow

1. **Feature Planning**: Every feature starts with a spec. Config changes MUST document schema evolution and OAuth scope implications. Auth changes MUST document token handling.
2. **Test-First**: Write acceptance tests first, approve with stakeholders (user stories), then implement. OAuth flows MUST be integration-tested.
3. **Code Review**: All PRs reviewed for (a) test coverage >80%, (b) no direct HTTP code, (c) OAuth tokens not logged, (d) config flow token validation, (e) Ruff pass, (f) README updated to reflect any user-facing changes (Principle VI).
4. **Integration Gates**: Config flow tests (including OAuth validation) + sensor platform tests MUST pass before merge.
5. **Release**: Version bumped according to semantic versioning; changelog documents breaking changes if MAJOR. OAuth scope changes require MAJOR version bump.

## Configuration Management

All configurable options are defined in a JSON schema in `manifest.json` and enforced by Home Assistant's config flow. OAuth tokens are managed separately via Home Assistant's credential system (not in `manifest.json`). Runtime configuration accessed via `ConfigEntry` and entity options. No environment variables or file-based config overrides allowed.

## Governance

This constitution supersedes all other development practices and guides all amendments to integration architecture, authentication security, testing discipline, and release procedures. Amendments require:

1. **Documentation**: Describe old vs. new principle with rationale
2. **Migration Plan**: Document how existing code/processes adapt (especially for auth changes)
3. **Review & Approval**: Documented in commit history

All code contributions MUST verify compliance with these principles. Exceptions require explicit justification in commit messages and PR discussions. OAuth security requirements are non-negotiable.

**Version**: 1.2.0 | **Ratified**: 2026-05-03 | **Last Amended**: 2026-06-01
