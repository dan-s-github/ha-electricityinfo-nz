<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:

**Active Feature**: OAuth Config Flow Authentication (001-oauth-config-flow)
**Plan Location**: `specs/001-oauth-config-flow/plan.md`

Key Design Documents:
- **Specification**: `specs/001-oauth-config-flow/spec.md` — User stories, requirements, success criteria
- **Research**: `specs/001-oauth-config-flow/research.md` — Technology decisions and patterns
- **Data Model**: `specs/001-oauth-config-flow/data-model.md` — Entity definitions and relationships
- **Config Flow Contract**: `specs/001-oauth-config-flow/contracts/config-flow.md` — UI/UX and OAuth flow steps
- **Wrapper Integration**: `specs/001-oauth-config-flow/contracts/wrapper-integration.md` — PyPI library integration
- **Quickstart**: `specs/001-oauth-config-flow/quickstart.md` — Developer setup and testing

**Constitution**: `.specify/memory/constitution.md` — 5 core principles (OAuth NON-NEGOTIABLE)

**Technology Stack**:
- Python 3.14+ with Home Assistant 2026.3.1
- OAuth 2.0 with requests-oauthlib
- electricityinfo-nz PyPI library for API calls
- pytest + pytest-asyncio for testing
- Home Assistant config flow framework for credential management

**Build Commands**:
```bash
uv sync                    # Install dependencies
pytest tests/              # Run tests
ruff check --fix           # Lint and fix
mypy custom_components/    # Type check
```

**Pre-commit Note**: Repository has pre-commit hooks that auto-fix formatting (trailing whitespace, EOF).
Changes made by hooks require re-staging and re-committing. This is expected behavior.

<!-- SPECKIT END -->
