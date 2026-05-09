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

Home Assistant custom integration for [Electricityinfo NZ](https://electricityinfo.co.nz) wholesale electricity prices. Track real-time and forecast spot prices at New Zealand grid reference nodes, directly in Home Assistant.

## Features

- **Current price sensor** — state is the current 30-minute trading period price
- **Forecast attribute** — upcoming prices as a time-series list (compatible with the `forecast_solar` convention)
- **Two unit entities per sensor** — NZD/MWh and c/kWh, created automatically
- **Multiple sensors** — add as many node/schedule combinations as you need
- **30-minute refresh cycle** — prices update every half-hour; state is restored on restart
- **HACS installable**

---

## Prerequisites

You need API credentials from [developer.electricityinfo.co.nz](https://developer.electricityinfo.co.nz):

1. Register for an account at the developer portal
2. Create an application to obtain a **Client ID** and **Client Secret**
3. The free tier is sufficient for personal Home Assistant use

---

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations → ⋮ → Custom repositories**
3. Add `https://github.com/dan-s-github/ha-electricityinfo-nz` as an **Integration**
4. Search for **Electricityinfo NZ** and install it
5. Restart Home Assistant

### Manual

1. Download the latest release from [GitHub Releases][releases]
2. Copy the `custom_components/electricityinfo` folder into your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

---

## Setup

### 1. Add the integration

Go to **Settings → Devices & Services → Add Integration** and search for **Electricityinfo NZ**.

Enter your **Client ID** and **Client Secret**. Home Assistant will validate the credentials against the API before saving.

### 2. Add price sensors

After the integration is set up, add price sensors via **Settings → Devices & Services → Electricityinfo NZ → Add sensor**.

Each sensor requires:

| Field | Description | Required |
|---|---|---|
| **Name** | Optional friendly name (e.g. "Haywards Energy") | No |
| **Schedule type** | The price schedule to track (see below) | Yes |
| **Market type** | Energy (`E`) or Reserve (`R`) | Yes |
| **Node** | Grid reference node (see below) | Yes |
| **Hours of forecast** | How many hours of forward prices to fetch (1–84 h) | No (default: 24 h) |

Each sensor you add creates a **device** with two entities — one in NZD/MWh and one in c/kWh.

To edit or remove a sensor, go to its device page and use the **⋮ → Reconfigure** or **Delete** options.

---

## Sensor Entities

### State

The sensor state is the **current trading period price** (the most recent 30-minute period returned by the API).

| Entity | Unit | Example state |
|---|---|---|
| `sensor.<name> NZD/MWh` | NZD/MWh | `87.45` |
| `sensor.<name> c/kWh` | c/kWh | `8.745` |

### Attributes

| Attribute | Description | Example |
|---|---|---|
| `timestamp` | ISO 8601 datetime of the current period | `2026-05-09T12:00:00+12:00` |
| `trading_period` | WITS trading period number (1–48) | `24` |
| `node` | Grid reference node code | `HAY2201` |
| `schedule` | Schedule type code | `RTD` |
| `run_type` | API run type | `actual` |
| `forecast` | List of upcoming prices (see below) | — |

### Forecast attribute

The `forecast` attribute is a list of future trading periods in the same format used by [forecast_solar](https://www.home-assistant.io/integrations/forecast_solar/):

```yaml
forecast:
  - period_start: "2026-05-09T12:30:00+12:00"
    price: 91.20
  - period_start: "2026-05-09T13:00:00+12:00"
    price: 88.50
  - period_start: "2026-05-09T13:30:00+12:00"
    price: 84.10
```

- `period_start` — ISO 8601 datetime with timezone
- `price` — price in the entity's unit (NZD/MWh or c/kWh)
- The **current period is not included** — only future periods appear here
- The number of entries is controlled by **Hours of forecast** (default 24 h = up to 48 entries)

---

## Schedule Types

| Code | Name | Description |
|---|---|---|
| `RTD` | Real-time dispatch | Live 5-minute dispatch prices (most current) |
| `Final` | Final | Final settled prices (after settlement) |
| `Interim` | Interim | Interim prices before final settlement |
| `PRSL` | Price-responsive long | Long-run price-responsive schedule |
| `PRSS` | Price-responsive short | Short-run price-responsive schedule |
| `NRSL` | Non-responsive long | Long-run non-responsive schedule |
| `NRSS` | Non-responsive short | Short-run non-responsive schedule |
| `WDS` | Weekly dispatch | Weekly dispatch schedule |

For most users, **RTD** (real-time dispatch) gives the most up-to-date prices.

---

## Grid Reference Nodes

Nodes are the grid injection/offtake points used by the WITS market. Choose the node geographically closest to you or relevant to your region.

| Code | Location | Island |
|---|---|---|
| `BRB0331` | Bream Bay | North Island |
| `OTA2201` | Otahuhu | North Island |
| `HLY2201` | Huntly | North Island |
| `WKM2201` | Waikamaka | North Island |
| `TUI1101` | Tuai | North Island |
| `SFD2201` | Stratford | North Island |
| `HAY2201` | Haywards | North Island |
| `STK2201` | Stoke | South Island |
| `DOB0661` | Dobson | South Island |
| `ISL2201` | Islington | South Island |
| `BEN2201` | Benmore | South Island |
| `HWB2201` | Hawea | South Island |
| `INV2201` | Invercargill | South Island |

---

## Usage Examples

### Lovelace — current price card

```yaml
type: entity
entity: sensor.haywards_energy_nzd_mwh
name: Spot Price
icon: mdi:flash
```

### Lovelace — forecast chart (ApexCharts)

With [ApexCharts Card](https://github.com/RomRider/apexcharts-card):

```yaml
type: custom:apexcharts-card
graph_span: 12h
series:
  - entity: sensor.haywards_energy_c_kwh
    attribute: forecast
    data_generator: |
      return entity.attributes.forecast.map(f => {
        return [new Date(f.period_start), f.price];
      });
```

### Automation — alert on high price

```yaml
alias: Alert when spot price is high
trigger:
  - platform: numeric_state
    entity_id: sensor.haywards_energy_c_kwh
    above: 20
action:
  - service: notify.mobile_app
    data:
      message: "⚡ Spot price is {{ states('sensor.haywards_energy_c_kwh') }} c/kWh"
```

### Template — next cheapest period

```yaml
template:
  - sensor:
      - name: Next cheap period
        state: >
          {% set forecast = state_attr('sensor.haywards_energy_c_kwh', 'forecast') %}
          {% if forecast %}
            {% set cheapest = forecast | min(attribute='price') %}
            {{ cheapest.period_start }}
          {% else %}
            unknown
          {% endif %}
```

---

## Update Behaviour

- Prices refresh every **30 minutes**, aligned with WITS trading periods
- On Home Assistant restart, the last known price is **restored immediately** (no waiting for first fetch) — provided the saved price is less than 30 minutes old
- If the API is unreachable, the integration retries after 1 minute, then marks sensors **unavailable** after a second failure; they recover automatically when the API returns

---

## Troubleshooting

**Sensors show "Unavailable"**
- Check your API credentials are still valid at [developer.electricityinfo.co.nz](https://developer.electricityinfo.co.nz)
- Check Home Assistant has internet access
- Check the integration logs: **Settings → System → Logs**, filter for `electricityinfo`

**Forecast is empty**
- The API may not have published forward prices for the selected node/schedule yet — this is normal for `Final` and `Interim` schedules which are published after settlement
- Try switching to `RTD` for the most consistently available forecast data

**Prices seem wrong**
- Wholesale spot prices are not retail prices — they are WITS market prices in NZD/MWh
- Divide by 1000 to get NZD/kWh, or use the c/kWh entity (NZD/MWh × 0.1)

---

## Development

```bash
uv sync              # install dependencies
pytest tests/        # run tests (mocked API)
ruff check --fix     # lint
mypy custom_components/  # type check
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

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
