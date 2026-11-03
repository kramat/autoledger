# AutoLedger

Automatic trip, charging and fuel bookkeeping for Home Assistant, with a web GUI that brings all costs and maintenance for all your cars together.

> **Status: milestone M3.** The add-on handles manual bookkeeping, charging, trips and a review inbox. The AutoLedger Collector integration records every drive with km, kWh, litres and cost, home charge sessions (priced with your live electricity price), refuels, public charging and climate & standby use, and can backfill the last days from the recorder. Next: reports and maintenance reminders (M4), see [docs/roadmap.md](docs/roadmap.md).

## What it does

- **Every drive, automatically.** Start and end time and place, km driven, kWh and litres used, and what that drive cost.
- **Every charge and refuel, automatically.** Home charging is read from the charger's kWh meter and priced with your live electricity price. Public charging and refuels are detected from the car and only need a price from you.
- **Manual vehicles too.** A car without Home Assistant data (for example a 2018 VW Up) gets fuel ups, odometer readings and maintenance entered by hand. It is included in every report just like a connected car.
- **Totals over any period.** km, kWh, litres, € and €/km, plus consumption (kWh/100 km, L/100 km), per vehicle or all vehicles together.
- **Maintenance and other costs.** A maintenance log with reminders by date and/or km, plus other costs such as insurance, road tax, parking and tolls.
- **You stay in control.** Every automatically found price or value can be corrected. Costs are recalculated from your corrections.

## Two parts

| Part | What it is | Where it runs | Job |
|---|---|---|---|
| **AutoLedger Collector** | Custom integration (install via HACS) | Inside Home Assistant Core | Watches the car and charger entities. Turns their state changes into *trips, charge sessions, refuels and odometer readings*. Sends those to the add-on and shows summary sensors back in HA. |
| **AutoLedger** | Home Assistant add-on | Its own container, managed by the Supervisor | The database, cost engine, web GUI (in the HA sidebar via Ingress) and REST API. Also handles manual entry, maintenance, other costs, reports and export. |

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

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Why two parts, how they find and talk to each other, data flow, failure handling |
| [Collector integration](docs/collector.md) | Setup, entity mapping, how trips, charges and refuels are detected, sensors, services, events |
| [Add-on & GUI](docs/addon.md) | Installation, options, every GUI page and what you can do on it |
| [Cost model](docs/costs.md) | How each euro is calculated: prices, battery and tank cost basis, consumption, recalculation |
| [Data model](docs/data-model.md) | Tables and fields |
| [API](docs/api.md) | REST API between the collector and the add-on (and for your own scripts) |
| [Reference setup](docs/my-setup.md) | Lynk & Co 01 PHEV + Shelly EV charger + VW Up: the concrete entity mapping and what the real data looks like |
| [Roadmap](docs/roadmap.md) | Milestones, lessons from v1, open questions |

## Requirements

- Home Assistant OS or Supervised. Add-ons need the Supervisor.
- Home Assistant 2025.6 or newer. The collector uses config subentries.
- For automatic tracking: a vehicle integration that exposes at least an odometer. A battery level, fuel level and location make it much more useful.
- For home charging: a charger or smart plug with a cumulative kWh sensor (`state_class: total_increasing`).

## Planned repository layout

```
autoledger/
├── README.md
├── docs/                          design + user documentation
├── custom_components/autoledger/  Collector integration (HACS)
├── addon/                         Add-on (Supervisor scans this folder)
│   ├── config.yaml
│   ├── Dockerfile
│   ├── backend/                   FastAPI + SQLAlchemy + Alembic
│   └── frontend/                  Vue 3 + Vite
├── repository.yaml                makes this repo an add-on repository
├── hacs.json                      makes this repo a HACS integration repository
└── .github/workflows/             tests, lint, add-on image builds
```

One repository serves both installers. HACS reads `custom_components/` and `hacs.json`, and the add-on store reads `repository.yaml` and `addon/`. Both parts share one version number.

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

MIT (to be added).
