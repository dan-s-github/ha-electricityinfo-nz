# Developer Quickstart: OAuth Config Flow

**Phase**: Phase 1 Design
**Date**: 2025-05-03

## Quick Setup for Developers

### Prerequisites

- Python 3.14+
- Home Assistant 2026.3.1 or later
- `electricityinfo-nz` PyPI library installed
- OAuth credentials from https://developer.electricityinfo.co.nz

### Project Structure

```
custom_components/electricityinfo/
├── __init__.py              # Integration entry point
├── config_flow.py           # OAuth config flow implementation
├── const.py                 # Constants and configuration
├── manifest.json            # Integration metadata
├── strings.json             # User-facing strings
└── strings/en.json          # English strings

tests/
├── conftest.py              # Pytest fixtures
├── test_config_flow.py      # Config flow tests
├── test_init.py             # Integration setup tests
└── test_oauth.py            # OAuth token tests
```

---

## 1. Project Setup

### Clone Repository

```bash
cd /path/to/home-assistant/custom_components
git clone https://github.com/dan-s-github/ha-electricityinfo-nz.git electricityinfo
cd ha-electricityinfo-nz
```

### Install Dependencies

```bash
# Use uv (package manager)
uv sync

# Or use pip
pip install -e .
pip install -r pyproject.toml[dev]
```

### Verify Installation

```bash
python -c "import electricityinfo_nz; print('Library OK')"
python -c "from homeassistant import config_entries; print('Home Assistant OK')"
```

---

## 2. Understanding the Config Flow

### OAuth Flow Overview (Client Credentials)

```
User Input (Step 1: Credentials)
  ↓
Exchange for Token (Step 2: Validate)
  ↓
Validate Token Works
  ↓
Create Config Entry
```

**Key Difference**: No browser redirects! Direct backend-to-backend token exchange.

### Key Interfaces

**Config Flow Class** (`config_flow.py`):
```python
class ElectricityInfoConfigFlow(config_entries.ConfigFlow):
    VERSION = 1
    async def async_step_user(self, user_input):
        # Step 1: Collect client_id and client_secret

    async def async_step_auth_validate(self):
        # Step 2: Exchange credentials for token and validate
```

**Integration Setup** (`__init__.py`):
```python
async def async_setup_entry(hass, config_entry):
    # Store credentials for later API access
    hass.data[DOMAIN] = {
        CONF_CLIENT_ID: config_entry.data[CONF_CLIENT_ID],
        CONF_CLIENT_SECRET: config_entry.data[CONF_CLIENT_SECRET],
    }
```

---

## 3. Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test File

```bash
pytest tests/test_config_flow.py -v
```

### Run Single Test

```bash
pytest tests/test_config_flow.py::test_user_form -v
```

### Run with Coverage

```bash
pytest tests/ --cov=custom_components/electricityinfo
```

### Mock Objects in Tests

```python
from unittest.mock import patch, AsyncMock

@patch("custom_components.electricityinfo.config_flow.OAuth2ClientCredentials")
async def test_token_exchange_success(mock_oauth, hass):
    mock_instance = AsyncMock()
    mock_instance.get_token.return_value = "test-token"
    mock_oauth.return_value = mock_instance
    # ... test code
```

---

## 4. Linting & Code Quality

### Run Linter (Ruff)

```bash
ruff check custom_components tests
```

### Fix Linting Issues

```bash
ruff check --fix custom_components tests
```

### Type Checking (Mypy)

```bash
mypy custom_components/electricityinfo
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

---

## 5. Common Development Tasks

### Add New Config Flow Step

**File**: `custom_components/electricityinfo/config_flow.py`

```python
async def async_step_new_step(self, user_input=None):
    """Handle new step."""

    if user_input is not None:
        # Process input
        return self.async_create_entry(title="...", data=user_input)

    # Show form
    return self.async_show_form(
        step_id="new_step",
        data_schema=vol.Schema({...}),
        description_placeholders={...}
    )
```

### Add New User-Facing String

**File**: `custom_components/electricityinfo/strings.json`

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Step title",
        "description": "Step description"
      }
    }
  }
}
```

### Add New Test

**File**: `tests/test_config_flow.py`

```python
@pytest.mark.asyncio
async def test_new_scenario(hass):
    """Test new scenario."""

    # Arrange
    # Act
    # Assert
```

---

## 6. Debugging

### Enable Debug Logging

**In Home Assistant configuration.yaml**:
```yaml
logger:
  default: info
  logs:
    custom_components.electricityinfo: debug
    homeassistant.config_entries: debug
```

### View Logs

```bash
# If using Docker
docker logs homeassistant | grep electricityinfo_nz

# If running locally
tail -f /path/to/home-assistant/logs/home-assistant.log | grep electricityinfo
```

### Add Debug Statements

```python
_LOGGER.debug("Current state: %s", self.context)
_LOGGER.debug("Token expires at: %s", token.get("expires_in"))
```

### Inspect Config Entry

```python
# In config_flow
_LOGGER.debug("Config entry data: %s", self.hass.config_entries.async_entries())
```

---

## 7. Common Issues & Solutions

### Issue: "Cannot connect to provider"

**Causes**:
- Network connectivity issue
- Provider API down
- Invalid redirect URI

**Solution**:
```bash
# Check network
ping developer.electricityinfo.co.nz

# Check redirect URI in config
# Should be: https://your-ha-domain/auth/authorize_callback
```

### Issue: "Token validation failed"

**Causes**:
- Invalid access token
- Token expired
- electricityinfo-nz library not installed

**Solution**:
```bash
# Verify library installed
python -c "import electricityinfo_nz; print('OK')"

# Check token format
_LOGGER.debug("Token: %s...", token[:20])  # Log first 20 chars only!
```

### Issue: Test fails with "No module named..."

**Causes**:
- Dependencies not installed
- Wrong Python version

**Solution**:
```bash
# Reinstall dependencies
uv sync --upgrade

# Check Python version
python --version  # Should be 3.14+
```

---

## 8. Integration Checklist

Before submitting for merge:

- [ ] All tests pass: `pytest tests/`
- [ ] No linting errors: `ruff check --fix`
- [ ] Type checking passes: `mypy custom_components/electricityinfo_nz`
- [ ] No secrets in logs: `grep -r "token\|secret" tests/`
- [ ] Config flow works end-to-end
- [ ] Token validation works
- [ ] Error scenarios handled gracefully
- [ ] User-friendly error messages
- [ ] Documentation updated
- [ ] Code commented where necessary

---

## 9. Reference Documents

- **Feature Spec**: `specs/001-oauth-config-flow/spec.md`
- **Data Model**: `specs/001-oauth-config-flow/data-model.md`
- **Config Flow Contract**: `specs/001-oauth-config-flow/contracts/config-flow.md`
- **Wrapper Integration**: `specs/001-oauth-config-flow/contracts/wrapper-integration.md`
- **Research**: `specs/001-oauth-config-flow/research.md`

---

## 10. Next Steps

After completing OAuth config flow:

1. **Phase 2**: Implement sensors
   - Energy price sensor
   - Grid generation sensor
   - Demand sensor

2. **Phase 3**: Add automations
   - Trigger on price changes
   - Adjust based on generation

3. **Phase 4**: HACS release
   - Prepare for Home Assistant Community Store
   - Documentation site

---

## Quick Reference: File Locations

| File | Purpose |
|------|---------|
| `__init__.py` | Integration setup (async_setup_entry) |
| `config_flow.py` | OAuth flow steps |
| `const.py` | Constants (DOMAIN, VERSION, URLs) |
| `manifest.json` | Integration metadata |
| `strings.json` | User-facing strings |
| `test_config_flow.py` | Config flow tests |
| `test_init.py` | Setup tests |
| `conftest.py` | Pytest fixtures |

---

## Support

For issues or questions:

1. Check existing GitHub issues
2. Review research.md for design decisions
3. Check data-model.md for entity relationships
4. Review config-flow.md for OAuth flow details

---

Last Updated: 2025-05-03
Phase: Phase 1 Design Complete
Next Phase: Phase 2 Task Generation
