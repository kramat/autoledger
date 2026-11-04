# History

AutoLedger was built in five milestones between 1 and 4 November 2026, each ending with something usable. The manual workflow came first, so the VW Up could be tracked from day one, before any automation existed. Release notes per version are in the [add-on changelog](../addon/CHANGELOG.md).

| Milestone | Release | Scope |
|---|---|---|
| **M1: Add-on core** | 0.1.0 | Add-on skeleton (Ingress, `/data`, migrations), vehicles, refuels, odometer readings, maintenance log, expenses, overview, fuel and maintenance pages, cost engine for refuels, CSV export |
| **M2: Collector, charging & fuel** | 0.2.0 | Collector config flow (discovery + manual), vehicle and charger subentries, snapshot builder, home charge detector with per-increment pricing, refuel and public charge detection, outbox, ingest API, review inbox, summary sensors |
| **M3: Trips** | 0.3.0 | Trip detector (snapshot mode), climate & standby records, kWh-per-% learning, battery and tank cost basis, fuel reconciliation, trips page with map, merge and split, backfill service |
| **M4: Insight** | 0.4.0 | Reports (period, compare, trends), maintenance schedules and reminders, XLSX export, JSON backup/restore, CSV import |
| **M5: Extras** | 0.5.0 | Snapshot boost, receipt photo attachments, depreciation, fuel price entity support |
| Finishing | 0.5.1–1.0.0 | Layout for foldables and narrow screens, the app icon, the Dutch translation, documentation, 1.0 |

## M1: Add-on core (2 Nov 2026)

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
- The image was first built by the Supervisor on the real installation; CSV import and maintenance schedules followed in 0.4.0.

## M2: Collector, charging & fuel (2 Nov 2026)

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

  HA's pytest plugin does not run on Windows, so the config flow is tested end to end, not with unit tests.
- **Collector 0.2.1:** vehicle values (type, tank, battery, wall kWh per %) follow the add-on on every summary poll instead of being copied once when the vehicle is added.
- **Verified on the real installation (HA 2026.10.4, Supervisor 2026.10.5):** the Supervisor routes the `autoledger` discovery to the custom integration; the entry was set up without pasting the token.

## M3: Trips (3 Nov 2026)

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

## 0.3.1 (3 Nov 2026)

- Fuel gauge noise smoothing: the tank level between refuels is fitted with the closest non-increasing line, and trips get its drop (docs/costs.md#fuel-gauge-noise). The correction at a full tank is spread by provisional litres instead of km, so electric PHEV trips stay at 0 L.

## M4: Insight (3 Nov 2026)

- **Add-on 0.4.0:**
  - migration 0004: `maintenance_schedules`, and `maintenance_records.schedule_id`;
  - due logic (`maintenance.py`): the latest of the starting point and the records that fulfil a schedule (linked, or by category), due by date and/or km, km-based dates estimated from the driving rate of the last 90 days, status `ok`/`soon`/`overdue`/`unknown`; `/maintenance-schedules` with `due`, `/maintenance-schedules/due`, and `maintenance`, `next_maintenance` and `car_service` in the summary;
  - ingest of `service.status` (the car's own countdown), kept per vehicle in `settings`;
  - reports: `/reports/period` (month, quarter, year), `/reports/compare` with figures per year, `/reports/trends` with seasons, exported as XLSX or CSV;
  - XLSX export per type and of all records (openpyxl), JSON `/backup` and `/restore` (empty or merge, with a database copy first), CSV import with a preview, column guessing (English and Dutch), decimal commas, date orders and duplicate detection;
  - GUI: Schedules on the Maintenance page (status, next due, *Log as done*, the car's countdown), next maintenance on the overview, a Reports page (year report, cars side by side, cost per group, trends, winter and summer), Import, Backup and Restore in Settings.
- **Collector 0.4.0:**
  - `sensor.<car>_next_maintenance` (days), `binary_sensor.<car>_maintenance_due`, event `autoledger_maintenance_due` once per schedule when it becomes soon and again when overdue, remembered in the store;
  - optional roles `days_to_service` and `distance_to_service`, sent as `service.status` when they change, only to an add-on that knows maintenance (0.4.0 or later).
- **Tests:** 91 add-on tests (due logic, schedules API, reports adding up, XLSX, backup round trip, CSV import) and 32 Collector engine tests. The dev database migrated from 0003 to 0004 with its backup, and its JSON backup restored into a fresh add-on gives identical summary, report, due list and trips.

## M5: Extras (3 Nov 2026)

- **Add-on 0.5.0:**
  - migration 0005: `attachments` (per resource and record, file under `/data/attachments/`), and `resale_estimate`, `resale_date`, `depreciation_enabled` on vehicles, added with plain `ADD COLUMN` (a batch copy of `vehicles` fails on its foreign keys);
  - `/attachments`: raw-body upload (no multipart dependency), inline serving with `nosniff`, soft delete with undo; refuels, maintenance and expenses list their attachments; `/backup?attachments=true` includes the files, `/restore` writes them back when the checksum matches;
  - depreciation in the ledger (`depreciation_cost`, part of `total_cost`), straight-line per month from the tracking start, in the summary, reports and exports;
  - GUI: *Add photo or PDF* in the refuel, maintenance and cost dialogs (photos over 1.5 MB shrunk to a 2000 px JPEG in the browser), a 📎 column, ownership fields on Vehicles, *Depreciation* in the overview and reports (it shares the "Other" bar in charts: four colors only), backup with files;
  - fix: the screen-reader "Actions" table headers widened every page with a table to 980 px on phones.
- **Collector 0.5.0:**
  - snapshot boost on local hints: home charger start (at once) and stop (+2 min), a chosen person leaving (at once) or arriving home (+2 and +10 min); one call per minute at most, `boost_max_per_day` per local day, decisions in the diagnostics; the action is suggested from the odometer's integration and checked when saving;
  - `fuel_price` role: the entity's €/L becomes the suggested price of a detected refuel.
- **Tests:** 99 add-on tests (depreciation math and API, attachments, backup with files) and 34 Collector engine tests (boost limits and presence hints). The dev database migrated from 0004 to 0005 with its backup and no schema difference to the models.

## 0.5.1 – 1.0.0 (4 Nov 2026)

- **0.5.1:** on screens narrower than 560 px (a folded Galaxy Z Fold, most phones) record tables show each row as a card; wider screens keep tables, with the actions column sticky on the right.
- **0.5.2:** the app icon, as the add-on's `icon.png` / `logo.png` and the Collector's `brand/` images (shown by HA 2026.3 and later).
- **0.6.0:** Dutch for the whole interface (a small built-in `t()` with type-checked texts), the API messages (`Accept-Language`), the add-on options and the Collector (`translations/nl.json`), with a language setting that defaults to the browser's language.
- **1.0.0:** the documentation rewritten to describe the finished product (checked against the code), vehicles marked as Collector vehicles when the Collector delivers their data (migration 0006 fixes existing ones), and the unused charger option `start_w` and vehicle role `plug_state` removed.
- **Collector 1.0.1:** on the real installation the first night charge never ended: after the car was full the Shelly drew about 2.8 W, and every tiny counter rise kept the session open. A rise slower than `stop_w` now counts as standby.

## Ideas that were not built

- **Live trip mode:** a trip that opens when the car's `running` sensor turns on. The Lynk's sensor never changes, and snapshot boost covers the same need for cloud cars.
- **Refuel confirmation with the tank flap**, and a better start time for trips than "last seen parked".
- **Data-quality checks** in the review inbox: km missing between trips (for example while HA was down), and consumption far above the average. The add-on already counts odometer readings it ignores, but the GUI does not show that count.
- **A Repair issue for overdue maintenance**, next to the existing sensor and event.
- **Recurring costs in the CSV import**, a price curve per home charge session, and backfilling home charge sessions from history.
- **CI**: `hassfest`, HACS validation and config-flow tests on GitHub's Linux runners.

## Testing

- **Collector:** unit tests per detector, fed with recorded state sequences, including the real Lynk sequence of 2 Nov and a Shelly power-flap sequence; the setup flow was tested end to end in a real Home Assistant core.
- **Add-on:** API tests and ledger tests, including the 2 Nov worked example; every migration was run against a copy of a real database.
- Every HA entity uses valid device class, state class and unit combinations: currency `EUR`, monetary with `total`, and €/km without a device class.
- All timestamps are timezone-aware, and no record can have a silent `None` → 0 conversion.

## Lessons from v1 (Car Cost Calculator) and how this design avoids them

| v1 problem | v2 answer |
|---|---|
| Options flow crashed, and saved options were never read | Subentries with reconfigure. Every setting has one location and one reader. |
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
| GUI language | English first. Dutch added in 0.6.0 (GUI, API messages, Collector). |
| Old data | Entered by hand with back-dated entries at first; CSV import arrived in 0.4.0. In the end there was nothing to import. |
| Repository | A new repo, `kramat/autoledger`. `HA_AutoLedger` stays as it is. |
