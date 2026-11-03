# REST API

The add-on serves a versioned JSON API. The collector uses it, the GUI uses it, and your own scripts can use it too. The generated OpenAPI spec is available at `/api/v1/openapi.json`, and a browsable version at `/api/v1/docs`.

## Basics

| | |
|---|---|
| Base URL (from HA) | `http://local-autoledger:8099/api/v1`. The hostname depends on how the add-on was installed; discovery provides it. |
| Base URL (from GUI) | `<ingress path>/api/v1`. Ingress has already authenticated the user. |
| Auth | `Authorization: Bearer <token>` for every non-Ingress request |
| Format | JSON, UTF-8, timestamps in ISO 8601 UTC, decimals as numbers |
| IDs | UUIDv7 strings (time-ordered) |
| Lists | `?limit=500&offset=0`, plus filters `vehicle_id`, `from` and `to` (local dates, inclusive) and `include_deleted`. The response is `{ "items": [...], "total": 123 }`. Each resource has a fixed sort order, newest first. |
| Errors | `{ "error": { "code": "validation_error", "message": "...", "fields": { "litres": "must be > 0" } } }` with status 400/401/403/404/409/422. A rule that spans several fields reports under the key `_`. |
| Concurrency | Every record has `version`. A `PATCH` that sends `If-Match: <version>` fails with `409` when the record has changed since. Without the header, the last write wins. |
| PATCH | Send only the fields you change. The body is merged onto the stored record and validated as a whole. For a refuel, the value you did not send among litres, price and total is recalculated. |

## System

| Method | Path | Purpose |
|---|---|---|
| GET / PUT | `/settings` | Currency and default prices |
| GET | `/settings/token` | The API token. Only through Ingress. |
| POST | `/settings/token/regenerate` | A new API token. Only through Ingress. |
| GET | `/info` | `{ name, version, api_version, currency, timezone }`. The collector checks compatibility with this. |
| GET | `/health` | Liveness check for the Supervisor watchdog |

## Ingest (collector → add-on, M2)

`POST /ingest` takes `{ "events": [...] }`, a batch of up to 100 events. It responds `200 { accepted: [{uuid, record_id}], duplicates: [uuid…], rejected: [{uuid, error}] }`. A rejected event is logged in the add-on and also creates a review item, so it is never dropped silently.

Event envelope:

```json
{
  "uuid": "0193f6c2-7a1e-7c3b-9d10-5be1f2a3c4d5",
  "type": "trip.recorded",
  "vehicle_id": "0193f0aa-…",
  "source": "collector",
  "collector_version": "0.1.0",
  "occurred_at": "2026-11-02T12:42:56Z",
  "payload": { }
}
```

| `type` | Payload (main fields) |
|---|---|
| `trip.recorded` | `start_ts`, `start_ts_estimated`, `end_ts`, `start: {lat, lon, address, zone}`, `end: {…}`, `odometer_start`, `odometer_end`, `distance_km`, `distance_source` (`trip_meter`/`odometer`), `battery_start_pct`, `battery_end_pct`, `charged_kwh`, `fuel_start_l`, `fuel_end_l`, `kind`, `flags` |
| `charge.started` / `charge.updated` / `charge.completed` | `session_id`, `charger_id`, `start_ts`, `end_ts`?, `energy_kwh`, `cost`, `price_samples: [{ts, kwh, price}]` (only in `completed`), `soc_start`?, `soc_end`? |
| `charge.soc_update` | `session_id`, `soc_start`?, `soc_end`?. Sent later, once the cloud car has reported its battery level. |
| `external_charge.detected` | `window_start`, `window_end`, `place`, `battery_start_pct`, `battery_end_pct`, `energy_kwh_estimated`, `car_reported_charging`, `flags: [...]` |
| `refuel.detected` | `ts`, `place`, `odometer`, `fuel_start_l`, `fuel_end_l`, `litres_estimated`, `suggested_price_per_l`, `price_source` |
| `idle.recorded` | `start_ts`, `end_ts`, `zone`, `battery_start_pct`?, `battery_end_pct`?, `fuel_start_l`?, `fuel_end_l`? |
| `service.status` | `days_to_service`, `distance_to_service` (km), `odometer_km`. The car's own service countdown (M4); the latest is kept per vehicle. |
| `odometer.reading` | `ts`, `odometer_km` |

Ingest rules:

- Duplicates (same `uuid`) are ignored.
- For a `charge.*` event, the newest values win for the same `session_id`, unless the user has locked those fields.
- `charge.completed` may arrive before `charge.started` after an outbox replay. The add-on handles any order.

## Resources

Each resource supports `GET` (list), `GET /{id}`, `POST`, `PATCH /{id}` and `DELETE /{id}` (soft delete). `POST /{id}/restore` undoes a delete.

| Path | Milestone | Notes |
|---|---|---|
| `/vehicles` | M1 | All vehicles, archived ones included (`archived_at`). `PATCH {"archived": true}` archives. |
| `/trips` | M3 | Items carry a `costing` block (see [costs.md](costs.md#recalculation)). `POST /trips/{id}/split {at_km, at_ts, address?}` returns both parts; `POST /trips/merge {ids:[a,b]}` merges two adjacent trips of one vehicle. The originals are soft-deleted, so `/restore` undoes either. |
| `/idle-records` | M3 | Climate & standby, with `costing` |
| `/charges` | M2 | Home, public and manual sessions. `price_mode` is `samples` (priced by the collector), `per_kwh`, `total` or `free`; `cost` is derived from it. |
| `/refuels` | M1 | List items include `interval_km` and `l_per_100km` on refuels that close a full-to-full interval |
| `/odometer-readings` | M1 | |
| `/maintenance` | M1 | Maintenance records (attachments from M5) |
| `/maintenance-schedules` | M4 | List items carry `due` (status `ok`/`soon`/`overdue`/`unknown`, `due_date`, `due_km`, `km_left`, `estimated_date`, `reason`, `days_left`). `GET /maintenance-schedules/due?vehicle_id=` gives the active schedules per vehicle, most urgent first, with `odometer_km`, `km_per_day` and the car's own `car_service` countdown. A maintenance record can name its `schedule_id`; without one it counts for the schedules of its category. |
| `/expenses` | M1 | One-off and recurring |
| `/attachments` | M5 | `POST` multipart upload. Returns an id to link from records. |
| `/review-items` | M2 | `GET` lists open items with the current `record`. `POST /review-items/{id}/resolve {action, values}` with action `update` (values are applied like a PATCH), `accept`, `delete` (the record) or `dismiss`. |

## Derived data

| Method | Path | Purpose |
|---|---|---|
| GET | `/summary?vehicle_id=&from=&to=&months=12` | **M1.** Per vehicle and combined: totals for the period, the last 12 months, a monthly series, latest odometer and last refuel. From M2 also last trip, next maintenance, review count and open sessions. |
| GET | `/reports/period?vehicle_id=&vehicle_ids=&from=&to=&group=month` | **M4.** Per vehicle and combined: `total`, `per_year` (scaled to 365 days) and `groups` (`month`, `quarter`, `year` or `none`), each with the same fields as the summary totals. Defaults to this year up to today. `/reports/period.xlsx` and `.csv` export it. |
| GET | `/reports/compare?vehicle_ids=a,b&from=&to=` | **M4.** The same without groups |
| GET | `/reports/trends?vehicle_id=&months=` | **M4.** Per vehicle: a monthly series of €/km and consumption since the first data (or the last `months`), and `seasons` (winter, spring, summer, autumn) summed over all months |
| GET | `/records/{id}/explain` | Cost breakdown of one record: inputs, prices used, cost basis at that moment |
| POST | `/ledger/recalculate?vehicle_id=&from=` | Forces a recalculation. This is normally automatic. |

## Export and backup

| Method | Path | Purpose |
|---|---|---|
| GET | `/export/{resource}.csv` / `.xlsx` | Same filters as the list endpoint |
| GET | `/export/records.xlsx` | **M4.** Every record type in one workbook, a sheet each |
| GET | `/backup` | **M4.** Every table as JSON (`format`, `format_version`, `schema_revision`, `tables`), deleted records included, the API token not. Attachments follow with M5. |
| POST | `/restore?mode=empty` or `merge` | **M4.** The backup as the JSON body. `empty` (default) needs a database without vehicles; `merge` adds the rows whose id is missing and keeps the rest. A backup from a newer version is refused. The database is copied to `/data/backups/autoledger-before-restore-<time>.db` first. Returns `{inserted, skipped}` per table. |
| POST | `/import/csv` | **M4.** JSON body `{resource, vehicle_id, content, mapping?, delimiter?, decimal?, date_order?}` for `refuels`, `maintenance`, `odometer-readings` or `expenses`. Without a mapping the columns are guessed (English and Dutch headers). Returns a preview (`mapping`, `decimal`, `date_order`, the first 50 `rows` with status `ok`/`error`/`duplicate`, `counts`); `?commit=true` imports the `ok` rows with `source: import`. |
