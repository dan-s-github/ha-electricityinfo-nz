# Electricityinfo NZ

[![HACS][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![Integration Usage][downloads-shield]][downloads]

[![Home Assistant][ha-shield]][ha]
[![Python Version][python-shield]][python]
[![License][license-shield]](LICENSE)

[![Tests][tests-shield]][tests]
[![Code Style: Ruff][ruff-shield]][ruff]
[![GitHub Activity][commits-shield]][commits]

Home Assistant custom integration scaffold.

## Features

- Config flow scaffold
- Config entry lifecycle scaffold
- Optional sensor platform scaffold
- Test scaffold for config flow, setup/unload, and optional sensor platform

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS.
2. Install `Electricityinfo NZ`.
3. Restart Home Assistant.
4. Add the integration from Settings -> Devices & Services.

### Manual

1. Copy `custom_components/electricityinfo_nz` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from Settings -> Devices & Services.

## Development

```bash
./scripts/setup
./scripts/lint
pytest
```

[releases-shield]: https://img.shields.io/github/release/dan-s-github/ha-electricityinfo-nz.svg?style=flat&logo=github
[releases]: https://github.com/dan-s-github/ha-electricityinfo-nz/releases
[downloads-shield]: https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=%24.electricityinfo_nz.total
[downloads]: https://analytics.home-assistant.io/custom_integrations/electricityinfo_nz
[commits-shield]: https://img.shields.io/github/commit-activity/y/dan-s-github/ha-electricityinfo-nz.svg?style=flat&logo=github
[commits]: https://github.com/dan-s-github/ha-electricityinfo-nz/commits/main
[license-shield]: https://img.shields.io/github/license/dan-s-github/ha-electricityinfo-nz.svg?style=flat
[python-shield]: https://img.shields.io/badge/python-3.14+-blue.svg?style=flat&logo=python&logoColor=white
[python]: https://www.python.org/
[ha-shield]: https://img.shields.io/badge/Home%20Assistant-2026.3.0+-blue.svg?style=flat&logo=homeassistant&logoColor=white
[ha]: https://www.home-assistant.io/
[tests-shield]: https://img.shields.io/github/actions/workflow/status/dan-s-github/ha-electricityinfo-nz/ci.yml?branch=main&style=flat&logo=github
[tests]: https://github.com/dan-s-github/ha-electricityinfo-nz/actions/workflows/ci.yml
[ruff-shield]: https://img.shields.io/badge/code%20style-ruff-000000.svg?style=flat&logo=ruff&logoColor=white
[ruff]: https://github.com/astral-sh/ruff
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat&logo=homeassistant&logoColor=white
[issues]: https://github.com/dan-s-github/ha-electricityinfo-nz/issues
