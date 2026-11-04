# REST API

The add-on serves a versioned JSON API. The collector uses it, the GUI uses it, and your own scripts can use it too. The generated OpenAPI spec is available at `/api/v1/openapi.json`, and a browsable version at `/api/v1/docs`.

## Basics

| | |
|---|---|
| Base URL (from HA) | `http://local-autoledger:8099/api/v1`. The hostname depends on how the add-on was installed; discovery provides it. |
| Base URL (from GUI) | `<ingress path>/api/v1`. Ingress has already authenticated the user. |
| Auth | `Authorization: Bearer <token>` for every non-Ingress request. `/health` needs no token. |
| Format | JSON, UTF-8, timestamps in ISO 8601 UTC, decimals as numbers |
| IDs | UUIDv7 strings (time-ordered) |
| Lists | `?limit=500&offset=0` (at most 5000), plus filters `vehicle_id`, `from` and `to` (local dates, inclusive, on resources with a date or time) and `include_deleted`. The response is `{ "items": [...], "total": 123 }`. Each resource has a fixed sort order: newest first, except vehicles and maintenance schedules (oldest first). |
| Errors | `{ "error": { "code": "validation_error", "message": "...", "fields": { "litres": "must be > 0" } } }` with status 400/401/403/404/409/413/415/422. A rule that spans several fields reports under the key `_`. Messages are English; with `Accept-Language: nl` they are Dutch (`autoledger/i18n.py`), as are the row errors of a CSV import preview. |
| Concurrency | Every record has `version`. A `PATCH` that sends `If-Match: <version>` fails with `409` when the record has changed since. Without the header, the last write wins. |
| PATCH | Send only the fields you change. The body is merged onto the stored record and validated as a whole. For a refuel, the value you did not send among litres, price and total is recalculated. |

## System

| Method | Path | Purpose |
|---|---|---|
| GET / PUT | `/settings` | Currency, interface `language` (`auto`/`en`/`nl`) and default prices (`electricity_price`, `public_charge_price`, `fuel_prices: {petrol, diesel, lpg}`) |
| GET | `/settings/token` | The API token. Only through Ingress. |
| POST | `/settings/token/regenerate` | A new API token. Only through Ingress. |
| GET | `/info` | `{ name, version, api_version, currency, timezone, last_ingest_at }`. The collector checks compatibility with this. |
| GET | `/health` | Liveness check for the Supervisor watchdog |

## Ingest (collector → add-on)

`POST /ingest` takes `{ "events": [...] }`, a batch of up to 100 events. It responds `200 { accepted: [{uuid, record_id}], duplicates: [uuid…], rejected: [{uuid, error}] }`. A rejected event is logged in the add-on and also creates a review item, so it is never dropped silently.

Event envelope:

```json
{
  "uuid": "0193f6c2-7a1e-7c3b-9d10-5be1f2a3c4d5",
  "type": "trip.recorded",
  "vehicle_id": "0193f0aa-…",
  "source": "collector",
  "collector_version": "1.0.0",
  "occurred_at": "2026-11-02T12:42:56Z",
  "payload": { }
}
```

| `type` | Payload (main fields) |
|---|---|
| `trip.recorded` | `start_ts`, `start_ts_estimated`, `end_ts`, `start: {lat, lon, address, zone}`, `end: {…}`, `odometer_start`, `odometer_end`, `distance_km`, `distance_source` (`trip_meter`/`odometer`), `battery_start_pct`, `battery_end_pct`, `charged_kwh`, `fuel_start_l`, `fuel_end_l`, `kind`, `flags` |
| `charge.started` / `charge.updated` / `charge.completed` | `session_id`, `charger_key`, `charger_name`, `start_ts`, `energy_kwh`, `cost`; `end_ts` and `price_samples: [{ts, kwh, price, source}]` only in `completed`; `soc_start`?, `soc_end`? |
| `charge.soc_update` | `session_id`, `soc_start`?, `soc_end`?. Sent later, once the cloud car has reported its battery level. |
| `external_charge.detected` | `window_start`, `window_end`, `place`, `battery_start_pct`, `battery_end_pct`, `energy_kwh_estimated`, `car_reported_charging`, `flags: [...]` |
| `refuel.detected` | `ts`, `place`, `odometer_km`, `fuel_start_l`, `fuel_end_l`, `litres_estimated`, `suggested_price_per_l`, `price_source` |
| `idle.recorded` | `start_ts`, `end_ts`, `zone`, `battery_start_pct`?, `battery_end_pct`?, `fuel_start_l`?, `fuel_end_l`? |
| `service.status` | `days_to_service`, `distance_to_service` (km), `odometer_km`. The car's own service countdown; the latest is kept per vehicle. |
| `odometer.reading` | `ts`, `odometer_km` |

Ingest rules:

- Duplicates (same `uuid`) are ignored.
- For a `charge.*` event, the newest values win for the same `session_id`, unless the user has locked those fields.
- `charge.completed` may arrive before `charge.started` after an outbox replay. The add-on handles any order.

## Resources

Each resource supports `GET` (list), `GET /{id}`, `POST`, `PATCH /{id}` and `DELETE /{id}` (soft delete). `POST /{id}/restore` undoes a delete.

| Path | Notes |
|---|---|
| `/vehicles` | All vehicles, archived ones included (`archived_at`). `PATCH {"archived": true}` archives, `false` unarchives. |
| `/trips` | Items carry a `costing` block (see [costs.md](costs.md#recalculation)). `POST /trips/{id}/split {at_km, at_ts, address?}` returns both parts; `POST /trips/merge {ids:[a,b]}` merges two adjacent trips of one vehicle. The originals are soft-deleted, so `/restore` undoes either. |
| `/idle-records` | Climate & standby, with `costing` |
| `/charges` | Home, public and manual sessions. `price_mode` is `samples` (priced by the collector), `per_kwh`, `total` or `free`; `cost` is derived from it. |
| `/refuels` | Two of `litres`, `price_per_l` and `total` are enough; the third is calculated. List items include `interval_km` and `l_per_100km` on refuels that close a full-to-full interval. |
| `/odometer-readings` | |
| `/maintenance` | Maintenance records. A record can name its `schedule_id`; without one it counts for the schedules of its category. |
| `/maintenance-schedules` | List items carry `due` (status `ok`/`soon`/`overdue`/`unknown`, `due_date`, `due_km`, `km_left`, `estimated_date`, `reason`, `days_left`). `GET /maintenance-schedules/due?vehicle_id=` gives the active schedules per vehicle, most urgent first, with `odometer_km`, `km_per_day` and the car's own `car_service` countdown. |
| `/expenses` | One-off, or recurring with `recurrence` (`monthly`/`quarterly`/`yearly`) from `date` up to an optional `end_date` |
| `/review-items` | `GET` lists open items with the current `record` (`?include_resolved=true` adds resolved ones, `?vehicle_id=` filters). `POST /review-items/{id}/resolve {action, values}` with action `update` (values are applied like a PATCH), `accept`, `delete` (the record) or `dismiss`. |

List items of refuels, maintenance and expenses carry their `attachments`.

### Attachments

Receipt photos and invoices of refuels, maintenance records and expenses.

| Method | Path | Purpose |
|---|---|---|
| GET | `/attachments?resource=&record_id=` | A record's attachments, as a list |
| POST | `/attachments?resource=refuels\|maintenance\|expenses&record_id=&filename=` | Upload with the **raw file as the body** and its `Content-Type` (JPEG, PNG, WebP, HEIC/HEIF, GIF or PDF; no SVG), at most 20 MB |
| GET | `/attachments/{id}/file` | The file, inline (`?download=true` as a download) |
| DELETE | `/attachments/{id}` | Soft delete; the file is kept. `POST /attachments/{id}/restore` undoes it. |

## Derived data

| Method | Path | Purpose |
|---|---|---|
| GET | `/summary?vehicle_id=&from=&to=&months=12` | Per vehicle and combined: totals for the period (default this month up to today), the last 12 months, a monthly series, latest odometer, last refuel, last trip, last and open charge, the kWh-per-% factor, maintenance due and the car's service countdown, plus the review count. Without `vehicle_id`, archived vehicles are left out. |
| GET | `/reports/period?vehicle_id=&vehicle_ids=&from=&to=&group=month` | Per vehicle and combined: `total`, `per_year` (scaled to 365 days) and `groups` (`month`, `quarter`, `year` or `none`), each with the same fields as the summary totals. Defaults to this year up to today. `/reports/period.xlsx` and `.csv` export it. |
| GET | `/reports/compare?vehicle_ids=a,b&from=&to=` | The same without groups |
| GET | `/reports/trends?vehicle_id=&vehicle_ids=&months=` | Per vehicle: a monthly series of cost per km and consumption since the first data (at most 10 years, or the last `months`), and `seasons` (winter, spring, summer, autumn) summed over all months |

## Export and backup

| Method | Path | Purpose |
|---|---|---|
| GET | `/export/{resource}.csv` / `.xlsx` | One resource (`vehicles`, `refuels`, `odometer-readings`, `charges`, `trips`, `idle-records`, `maintenance`, `maintenance-schedules`, `expenses`), with the filters `vehicle_id`, `from` and `to` |
| GET | `/export/records.xlsx` | Every record type in one workbook, a sheet each, with the same filters |
| GET | `/backup` | Every table as JSON (`format`, `format_version`, `app_version`, `schema_revision`, `exported_at`, `tables`), deleted records included, the API token not. `?attachments=true` adds `files` (attachment id → base64). |
| POST | `/restore?mode=empty` or `merge` | The backup as the JSON body. `empty` (default) needs a database without vehicles; `merge` adds the rows whose id is missing and keeps the rest. A backup from a newer version is refused. The database is copied to `/data/backups/autoledger-before-restore-<time>.db` first. Returns `{mode, tables, files}`: `{inserted, skipped}` per table, and `{written, skipped}` for the files. A file is written when its row is there, the file is not, and the SHA-256 matches. |
| POST | `/import/csv` | JSON body `{resource, vehicle_id, content, mapping?, delimiter?, decimal?, date_order?}` for `refuels`, `maintenance`, `odometer-readings` or `expenses`. Without a mapping the columns are guessed (English and Dutch headers). Returns a preview (`mapping`, `delimiter`, `decimal`, `date_order`, the first 50 `rows` with status `ok`/`error`/`duplicate`, `counts`); `?commit=true` imports the `ok` rows, refuels and odometer readings with `source: import`. |
