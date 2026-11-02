# Architecture

## Goals

1. Record trips, charge sessions and refuels **without user action** for cars that are connected to Home Assistant.
2. Never lose or silently zero a record. That covers HA restarts, add-on updates, sensors that drop to `unavailable`, and sparse cloud data.
3. Give **one place** to see and correct everything, for connected and manual vehicles alike.
4. Make every cost **explainable**. For any euro in a report, the GUI can show which records and prices produced it.

## Non-goals

- Turn-by-turn route logging. We record start and end points, not the GPS track.
- Being a fleet or lease-administration product. There is no business/private ride registration.
- Replacing the HA Energy dashboard. AutoLedger reads the same meters but answers a different question: what does driving cost?

## Why two parts

| Concern | Collector (integration) | Add-on |
|---|---|---|
| Sees state changes the moment they happen | ✅ event-driven inside HA | ❌ would need a websocket client and reconnect logic |
| Uses HA concepts (zones, entity selectors, devices, notifications, services) | ✅ native | ❌ |
| Runs a web application with its own pages and routes | ❌ limited to Lovelace cards | ✅ Ingress panel in the sidebar |
| Holds years of records without bloating the recorder database | ❌ | ✅ own SQLite file |
| Works for vehicles HA knows nothing about | ❌ | ✅ |
| Can be updated or restarted independently | — | ✅ |
| Included in HA backups | ✅ `.storage` | ✅ add-on `/data` |

The collector is deliberately **thin**. It detects, packages and delivers events. All bookkeeping, pricing and reporting happens in the add-on. That means detection bugs can be fixed with a collector update, and cost-model changes with an add-on update. Neither change destroys data.

## Components

```
Collector (custom_components/autoledger)
├── config_flow.py        connection to the add-on + "vehicle" subentries + "charger" subentries
├── snapshot.py           builds a Snapshot from the mapped entities on every relevant change
├── detectors/
│   ├── trip.py           odometer / trip-meter deltas between snapshots → trips
│   ├── home_charge.py    charger kWh counter → charge sessions, priced per kWh increment
│   ├── external_charge.py battery % up without home kWh → public charge (needs price)
│   ├── refuel.py         fuel level jump → refuel (needs price)
│   └── idle.py           battery/fuel drop without km → idle consumption (climate, standby)
├── outbox.py             persisted queue of unsent events, retried with backoff
├── client.py             REST client for the add-on API
├── coordinator.py        polls /summary for the exposed sensors
├── sensor.py / binary_sensor.py
├── services.yaml         manual entry services
└── diagnostics.py

Add-on (addon/)
├── backend/
│   ├── api/              FastAPI routers (/api/v1/...)
│   ├── ingest/           validates and stores collector events, idempotent
│   ├── ledger/           cost engine: replays records per vehicle, cost basis, reconciliation
│   ├── reports/          aggregations, CSV/XLSX export
│   ├── reminders/        maintenance due calculation
│   └── db/               SQLAlchemy models + Alembic migrations
└── frontend/             Vue 3 single-page app, served under the Ingress path
```

## Data flow

### 1. Automatic records (collector → add-on)

```
state_changed ─► Snapshot builder (debounce 30 s) ─► Detectors ─► Event {uuid, type, vehicle_id, payload}
                                                                        │
                                       HA Store "autoledger.outbox" ◄───┘  (persisted before sending)
                                                                        │
                                       POST /api/v1/ingest (batch) ◄────┘  retry with backoff until 2xx
                                                                        │
                       add-on: store raw event ─► upsert record (trip / charge / refuel / …) ─► recalculate ledger
```

- Every event has a UUID that the collector generates. The add-on ignores a UUID it has already seen, so retries are always safe.
- An open charge session is sent as `charge.started`, then as `charge.updated` every 15 minutes, and finally as `charge.completed`. All three carry the same `session_id`, so the GUI shows a running session live and the record is never lost.
- The collector keeps its detector state (last snapshot, open sessions) in its own HA Store and writes it **before** an event goes into the outbox. A restart in the middle of anything resumes cleanly.

### 2. Manual records (user → add-on)

- Entered in the GUI. This is the normal way for the VW Up, maintenance and expenses.
- Or through collector services such as `autoledger.add_refuel`. These are useful from automations, NFC tags or a dashboard button. The collector just forwards them to the add-on API.

### 3. Summary back into HA (add-on → collector)

- The collector polls `GET /api/v1/summary` every 5 minutes, and right after it delivers events. It exposes the result as sensors: cost this month, €/km, open review items, next maintenance due, and so on.
- The add-on is the only place where totals are calculated, so HA sensors and the GUI always agree.

## Source of truth

| Data | Owner |
|---|---|
| Vehicles, trips, charges, refuels, odometer readings, maintenance, expenses, prices | **Add-on database** |
| Entity mapping (which HA entity is the odometer, and so on) | Collector config entry |
| Detector state (last snapshot, open session, outbox) | Collector HA Store |
| Costs, totals, consumption figures | **Derived** by the add-on from the records. They are never edited directly. |

Costs are always derived by **replaying** a vehicle's records in time order (see [costs.md](costs.md#recalculation)). When you correct one refuel price, every trip after it is re-priced and you never have to touch the other trips.

## Connection, discovery and security

- The add-on listens on port `8099` inside the Supervisor network. That port is **not** mapped to the host by default.
- **GUI access** goes only through Ingress. HA does the authentication, so there is no separate login.
- **API access** from the collector uses a bearer token. The add-on generates it on first start and stores it in `/data/secret.json`. You can regenerate it in the add-on's Settings page.
- **Discovery:** on start, the add-on registers itself with the Supervisor discovery API as service `autoledger`, sending its host, port and token. The collector's config flow handles the resulting `hassio` discovery, so setup is a single "Configure" click.
  - Fallback for when the Supervisor does not route discovery for a custom integration (to be verified in milestone M2): the collector's config flow asks for the URL (default `http://local-autoledger:8099` for a locally installed add-on) and the token, which the add-on shows on its Settings page.
- The collector checks the add-on's `api_version` from `GET /api/v1/info` and raises a Repair issue when the two versions are incompatible.

## Time and units

- Every timestamp is stored in **UTC** (ISO 8601 with `Z`) and shown in the HA time zone. Period boundaries in reports ("this month") use that local time zone.
- Distances are stored in km, energy in kWh, fuel in litres and money in the add-on's currency (default `EUR`). Values are stored as decimals with 4 places and rounded only for display.
- Where the car reports its own timestamp (for example the Lynk's `last_updated_by_car`), that is used as the event time instead of the moment HA received the value.

## Failure handling

| Situation | Behaviour |
|---|---|
| Add-on stopped or updating | Events wait in the outbox, which is persisted, and are delivered when the add-on is back. After 24 h of failed delivery the collector raises a Repair issue. |
| HA restarts while the car is parked | The last snapshot is restored. The next snapshot is compared against it, and everything that happened in between becomes normal events. |
| HA restarts during a home charge | The open session and its last valid kWh reading are restored. The kWh counter is cumulative, so nothing is missed. |
| A sensor goes `unavailable` or `unknown` | It is ignored. The last valid value is kept and its age is tracked. Deltas are only ever calculated between two valid readings. |
| Charger kWh counter resets (firmware update, replacement) | A drop in the counter is treated as a reset. The new value becomes the base, and nothing negative is recorded. |
| Cloud data is sparse or delayed (the Lynk case) | Trips are calculated per snapshot segment (see [collector.md](collector.md#trip-detection)). Uncertain cases go to the review inbox instead of being guessed silently. |
| A detector misfires | You can edit or delete the record in the GUI. Fields you edited are locked, and later collector updates for the same record never overwrite them. |

## Backups and migrations

- The add-on database lives in `/data/autoledger.db`, which is part of normal HA backups.
- Schema changes use Alembic migrations, which run automatically on add-on start. Before each migration the add-on copies the database to `/data/backups/autoledger-<version>.db`.
- The GUI offers a full JSON export and import for moving between installations.
