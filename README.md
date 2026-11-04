```text
                                                         _O
                                                       _/
                                        o            _/
                                       / \          /
                                      /   \    o___/
              _____________          /     \  /
          _.-'     |       `-.._    /       `o
       .-'_________|____________`. /
      |    .-.              .-.   |/
      '---( o )------------( o )--'
           `-'              `-'
    ___         __        __             __
   /   | __  __/ /_____  / /   ___  ____/ /___ ____  _____
  / /| |/ / / / __/ __ \/ /   / _ \/ __  / __ `/ _ \/ ___/
 / ___ / /_/ / /_/ /_/ / /___/  __/ /_/ / /_/ /  __/ /
/_/  |_\__,_/\__/\____/_____/\___/\__,_/\__, /\___/_/
                                       /____/

   trips  -  charging  -  fuel  -  maintenance  -  costs
```

<img src="assets/icon.svg" alt="" width="96" align="right">

# AutoLedger

Automatic trip, charging and fuel bookkeeping for Home Assistant, with a web app in the sidebar that brings all costs and maintenance of all your cars together.

## What it does

- **Every drive, automatically.** Start and end time and place, km driven, kWh and litres used, and what that drive cost, valued at what you actually paid for the energy in the battery and the tank.
- **Every charge and refuel, automatically.** Home charging is read from the charger's kWh meter and priced per kWh with your live electricity price. Public charging and refuels are detected from the car and only need the price you paid.
- **Manual vehicles too.** A car without Home Assistant data (for example a 2018 VW Up) gets its refuels, odometer readings and maintenance entered by hand, and is in every report just like a connected car.
- **Totals over any period.** km, kWh, litres, € and €/km, consumption (kWh/100 km, L/100 km), year reports, cars side by side, monthly trends and winter against summer.
- **Maintenance and other costs.** A maintenance log with schedules and reminders (as Home Assistant sensors and events), insurance, road tax, parking and tolls, recurring costs, depreciation and receipt photos.
- **You stay in control.** Everything found automatically can be corrected, and every cost is recalculated from your corrections. A review inbox lists what needs your input.
- **Your data stays yours.** Everything is in a local database included in Home Assistant backups, with Excel and CSV export, JSON backup and CSV import.
- **English and Dutch**, on desktop and phone (foldables included).

## How it works

| Part | What it is | Where it runs | Job |
|---|---|---|---|
| **AutoLedger Collector** | Custom integration (install via HACS) | Inside Home Assistant Core | Watches the car and charger entities and turns their state changes into trips, charge sessions, refuels and odometer readings. Sends those to the add-on and shows summary sensors back in HA. |
| **AutoLedger** | Home Assistant add-on | Its own container, managed by the Supervisor | The database, cost engine, web app (in the HA sidebar via Ingress) and REST API. Also handles manual entry, maintenance, other costs, reports and export. |

```
 ┌──────────────── Home Assistant Core ────────────────┐        ┌──────────── AutoLedger add-on ────────────┐
 │                                                     │        │                                          │
 │  Lynk & Co entities ─┐                              │ events │  REST API ──► SQLite (/data)             │
 │  Shelly EV charger ──┼─► AutoLedger Collector ──────┼───────►│                 │                        │
 │  Electricity price ──┘    (detectors + outbox)      │        │            Cost engine                   │
 │                                                     │summary │                 │                        │
 │  sensor.autoledger_* ◄──────────────────────────────┼◄───────┤  Web GUI (Ingress, HA sidebar)          │
 │  autoledger.* services ─────────────────────────────┼───────►│   overview · trips · charging · fuel     │
 │                                                     │        │   maintenance · costs · reports · review │
 └─────────────────────────────────────────────────────┘        └──────────────────────────────────────────┘
```

## Installation

1. **Add-on:** in Home Assistant, open **Settings → Add-ons → Add-on store → ⋮ → Repositories** and add `https://github.com/kramat/autoledger`. Install **AutoLedger**, turn on *Show in sidebar* and start it.
2. **Collector** (for automatic tracking): in HACS, open **⋮ → Custom repositories**, add the same URL with category *Integration*, download **AutoLedger Collector** and restart Home Assistant. It finds the add-on by itself.
3. Open **AutoLedger** from the sidebar, add your vehicles, and link the connected ones to their entities on the Collector's integration page.

The add-on's **Documentation** tab ([addon/DOCS.md](addon/DOCS.md)) walks through the rest.

## Requirements

- Home Assistant OS or Supervised: add-ons need the Supervisor.
- Home Assistant 2025.6 or newer for the Collector (config subentries); its icon shows from 2026.3.
- For automatic tracking: a vehicle integration that exposes at least an odometer. A battery level, fuel level and location make it much more useful.
- For home charging: a charger or smart plug with a cumulative kWh sensor (`state_class: total_increasing`).

## Documentation

| Document | Contents |
|---|---|
| [User guide](addon/DOCS.md) | Getting started, automatic tracking, the review inbox, maintenance, reports, receipts, language, backups (also the add-on's Documentation tab) |
| [Add-on & GUI](docs/addon.md) | Every page of the web app and what you can do on it |
| [Collector integration](docs/collector.md) | Setup, entity mapping, how trips, charges and refuels are detected, sensors, services, events |
| [Cost model](docs/costs.md) | How each euro is calculated: prices, battery and tank cost basis, consumption, depreciation, recalculation |
| [Architecture](docs/architecture.md) | Why two parts, how they find and talk to each other, data flow, failure handling |
| [Data model](docs/data-model.md) | Tables and fields |
| [REST API](docs/api.md) | The API between the Collector and the add-on, also for your own scripts |
| [Reference setup](docs/my-setup.md) | Lynk & Co 01 PHEV + Shelly EV charger + VW Up: the entity mapping and what the real data looks like |
| [History](docs/history.md) | How it was built, decisions, lessons from v1, ideas that were not built |
| [Changelog](addon/CHANGELOG.md) | What changed in each version |

## Repository layout

```
autoledger/
├── README.md
├── assets/icon.svg                source of the app icon
├── docs/                          reference documentation
├── custom_components/autoledger/  Collector integration (HACS), with its icon in brand/
├── addon/                         add-on (the Supervisor reads this folder)
│   ├── config.yaml, Dockerfile    add-on packaging
│   ├── DOCS.md, CHANGELOG.md      shown in the add-on store
│   ├── backend/                   FastAPI + SQLAlchemy + Alembic, with tests
│   └── frontend/                  Vue 3 + Vite, texts in src/i18n/
├── tests/collector/               Collector engine tests
├── repository.yaml                makes this repo an add-on repository
└── hacs.json                      makes this repo a HACS integration repository
```

One repository serves both installers: HACS reads `custom_components/` and `hacs.json`, the add-on store reads `repository.yaml` and `addon/`. A GitHub release tag (for example `v1.0.0`) is what HACS offers as an update.

## Development

Backend (Python 3.13+), from `addon/backend`:

```bash
uv venv .venv && uv pip install -r requirements-dev.txt --python .venv
```

```bash
.venv/Scripts/python -m pytest
```

Collector engine tests (Home Assistant test environment), from the repository root:

```bash
uv venv .venv-ha --python 3.14 && uv pip install --python .venv-ha pytest-homeassistant-custom-component
```

```bash
.venv-ha/Scripts/python -m pytest -p no:homeassistant
```

(`-p no:homeassistant` because HA's pytest plugin does not run on Windows; on Linux leave it out.)

Frontend (Node 22+), from `addon/frontend`:

```bash
npm ci && npm run build
```

Run the whole add-on locally on http://127.0.0.1:8099, with data in `dev-data/`:

```bash
addon/backend/.venv/Scripts/python addon/backend/dev_server.py
```

For frontend work with hot reload, run `npm run dev` next to the dev server. Vite proxies `/api` to port 8099.

## License

[MIT](LICENSE) © 2026 Bart Kramer
