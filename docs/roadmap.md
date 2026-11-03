# Roadmap

Each milestone ends with something usable. The manual workflow comes first, so the VW Up can be tracked from day one, before any automation exists.

| Milestone | Scope | Done when |
|---|---|---|
| **M1: Add-on core** ✅ built | Add-on skeleton (Ingress, `/data`, migrations), vehicles, refuels, odometer readings, maintenance log, expenses, overview + fuel + maintenance pages, cost engine for refuels, CSV export | The VW Up's refuels and maintenance can be logged and give L/100 km, €/km and monthly costs |
| **M2: Collector, charging & fuel** ✅ built | Collector config flow (discovery + manual), vehicle and charger subentries, snapshot builder, home charge detector with per-increment pricing, refuel and external charge detection, outbox, ingest API, review inbox, summary sensors | A night charge on the Shelly shows up with correct kWh and € even when the power sensor flaps. A refuel of the Lynk ends up in the review inbox. |
| **M3: Trips** ✅ built | Trip detector (snapshot mode), idle records, kWh-per-% learning, battery/tank cost basis, trips page with map, merge/split, backfill service | Every Lynk drive appears with km, kWh, L and €. The 2 Nov example reproduces the numbers in [costs.md](costs.md#worked-example-lynk--co-2-nov-2026). |
| **M4: Insight** | Reports (period, compare, trends), maintenance schedules and reminders, fuel reconciliation, XLSX export, JSON backup/restore, CSV import | Year report for both cars, and maintenance reminders as HA sensors |
| **M5: Extras** | Snapshot boost, live trip mode, receipt photo attachments, recurring expenses + depreciation, fuel price entity support | — |

## M1 as built (2 Nov 2026)

- Add-on packaging: `config.yaml` with Ingress, a watchdog on `/api/v1/health` and an optional API port. The Dockerfile is multi-stage: it builds the frontend with Node, then the Python image.
- Backend: FastAPI, SQLAlchemy 2 and SQLite (WAL), with Alembic migrations run on start and a database backup before each upgrade. The token is in `/data/secret.json`. Ingress requests are trusted, and every other caller needs the bearer token.
- Cost engine (`ledger.py`):
  - odometer timeline from the start value, readings, refuels and maintenance, linearly interpolated, with backwards values ignored;
  - full-to-full L/100 km;
  - fuel cost counted on purchase;
  - recurring expenses spread per month and pro rata.

  All of it is calculated in UTC, so DST changes are counted correctly.
- GUI: Overview (cards, a 12-month cost and distance chart, and a table view), Fuel (refuels, odometer readings), Maintenance log, Costs, Vehicles and Settings, plus CSV export and undo on delete. It is responsive and supports dark mode.
- Tests: 33 backend tests (ledger and API). The frontend is type-checked with `vue-tsc`.
- **Not in M1 / still to verify:**
  - the image has not been built by a real Supervisor yet; that happens on first install;
  - no CSV import yet (M4), so old data is entered by hand with back-dated dates;
  - maintenance schedules and reminders follow in M4.

## 0.3.1 (3 Nov 2026)

- Fuel gauge noise smoothing: the tank level between refuels is fitted with the closest non-increasing line, and trips get its drop (docs/costs.md#fuel-gauge-noise). The correction at a full tank is spread by provisional litres instead of km, so electric PHEV trips stay at 0 L.

## M3 as built (3 Nov 2026)

- **Add-on 0.3.0:**
  - migration 0003 (trips, idle records);
  - ingest of `trip.recorded` and `idle.recorded`;
  - cost engine: battery and tank pools with a weighted average price from the first trip on, engine-charged kWh at €0, fuel reconciliation between full tanks (only when trips cover ≥ 80 % of the km), kWh per % learned from home sessions with a plausibility filter;
  - trip-based totals: trip km, kWh/100 km, L/100 km, electric share, climate & standby kept out of €/km;
  - `/trips` with costing, split and merge (undoable), `/idle-records`, trips in the summary and CSV export;
  - GUI: Trips page (list, OpenStreetMap map, details with the cost calculation, split, merge, add by hand), climate & standby list, efficiency card on Charging, last trip and consumption on the overview.
- **Collector 0.3.0:**
  - trip detection per segment, with the trip meter only when it agrees with the odometer, round trips by zone or 150 m, and the energy charged within the window;
  - idle detection when parked and not charging;
  - `autoledger.backfill` from recorder history up to where live tracking began, with uuids derived from the content;
  - thresholds `min_trip_km`, `idle_min_pct`, `idle_min_l`; sensors `last_trip` and `electric_consumption`; event `autoledger_trip_recorded`.
- **Tests:** 59 add-on tests (the 2 Nov worked example gives €1.16 / €0.18 per km) and 30 Collector engine tests, plus the end-to-end run in a real HA core, now with backfill from the recorder and live trips.
- **Not built from the M3 design:** refining an estimated start time with an average speed (M5), a price curve per home session, backfilling home charge sessions, and a cache of the replay states (not needed yet).

## M2 as built (2 Nov 2026)

- **Add-on 0.2.0:**
  - migration 0002 (charge sessions, review items, ingest log, `kwh_per_pct`);
  - `POST /ingest`, idempotent by uuid, each event in its own savepoint, rejected events kept and put in review;
  - charge pricing modes;
  - review inbox with quick actions, where an edited automatic record confirms itself;
  - electricity in the totals;
  - Supervisor discovery announcement;
  - GUI: Charging and Review pages, an inbox counter, the live session on the overview, and wall kWh per % on vehicles.
- **Collector 0.2.0** (`custom_components/autoledger`):
  - config flow with discovery, manual URL suggestion, reconfigure and reauth;
  - vehicle and charger subentries, with entity suggestions from the odometer's device;
  - snapshot engine with sanitizing;
  - refuel, public charge and odometer detection;
  - home charge sessions from the kWh counter, priced per increment, persisted across restarts;
  - battery % at start from snapshot history and at the end from the car's next report;
  - persisted outbox with backoff and a Repair issue after 24 h;
  - summary sensors for every add-on vehicle, live charger entities, services, events and diagnostics.
- **Tests:**
  - 43 add-on tests and 25 Collector engine tests;
  - plus an end-to-end run in a real Home Assistant 2026.10.4 core against the dev add-on: config flow, both subentries, a night charge with a flapping power sensor, a refuel, discovery, a service call and diagnostics.

  HA's pytest plugin does not run on Windows, so config-flow unit tests for CI follow later.
- **Collector 0.2.1:** vehicle values (type, tank, battery, wall kWh per %) follow the add-on on every summary poll instead of being copied once when the vehicle is added.
- **Verified on the real installation (HA 2026.10.4, Supervisor 2026.10.5):** the Supervisor routes the `autoledger` discovery to the custom integration; the entry was set up without pasting the token.
- **Not verified yet:** behaviour on the real Lynk and Shelly data over a few days.

## Quality bar (all milestones)

- **Collector**: unit tests per detector, fed with recorded state sequences. These include the real Lynk sequence from 2 Nov and a Shelly power-flap sequence. It also gets config-flow tests with `pytest-homeassistant-custom-component`, plus `hassfest` and HACS validation in CI.
- **Add-on**: API tests and ledger property tests. One property: replaying the records in any insertion order gives the same costs. Alembic migration tests run against a copy of a real database.
- Every HA entity uses valid device class, state class and unit combinations: currency `EUR`, monetary with `total`, and €/km without a device class.
- All timestamps are timezone-aware, and no record can have a silent `None` → 0 conversion.

## Lessons from v1 (Car Cost Calculator) and how this design avoids them

| v1 problem | v2 answer |
|---|---|
| Options flow crashed, and saved options were never read | Subentries with reconfigure. Every setting has one location and one reader, and there are config-flow tests. |
| Cost/km was always 0, because distance was only counted while charging | Distance comes from trip meter and odometer deltas, independent of charging |
| Fuel level in litres was treated as a percentage | The unit is chosen explicitly in the mapping. Refuels are detected, and trips use litre deltas. |
| Charging energy came from a 60 s poll, so a flapping Shelly gave 0 kWh | Energy comes only from valid counter readings, with event-driven deltas |
| An open session was lost on restart | Detector state and outbox are persisted before sending |
| Electricity price was fixed | Price entity sampled per kWh increment, with manual override per session |
| Shared mutable defaults between cars | Each vehicle's records are rows in a database, not shared dicts |
| Invalid sensor classes and the "€" unit | Valid combinations, covered by tests |
| Free-text `entry_id` in services | Device selector |
| Mixed naive and UTC timestamps | UTC everywhere, timezone-aware |
| Placeholder manifest URLs and naming mismatch | One name (AutoLedger), real repository URLs, codeowners |

## Decisions (2 Nov 2026)

| Question | Decision |
|---|---|
| Lynk battery capacity | 14.1 kWh usable (17.6 kWh gross). An empty-to-full home charge takes ≈ 16.5 kWh, so the starting `kwh_per_pct` is 0.165. |
| Public charging | 1–2 times per month. These go through the review inbox; no charge-card integration is needed. |
| Business/private tagging | Not needed. It has been removed from the scope. |
| GUI language | English first. Dutch comes later. |
| Old data | There is history to import. In M1 it can be entered with back-dated entries; CSV import follows in M4. |
| Repository | A new repo, `kramat/autoledger`. `HA_AutoLedger` stays as it is. |
