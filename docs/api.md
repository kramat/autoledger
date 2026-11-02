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

`POST /ingest` takes a batch of up to 100 events. It responds `200 { accepted: [uuid…], duplicates: [uuid…], rejected: [{uuid, error}] }`. A rejected event is logged in the add-on and also creates a review item, so it is never dropped silently.

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
| `trip.recorded` | `start_ts`, `start_ts_estimated`, `end_ts`, `start: {lat, lon, address, zone}`, `end: {…}`, `odometer_start`, `odometer_end`, `distance_km`, `distance_source` (`trip_meter`/`odometer`), `battery_start_pct`, `battery_end_pct`, `energy_kwh`, `fuel_start_l`, `fuel_end_l`, `fuel_l`, `kind` |
| `charge.started` / `charge.updated` / `charge.completed` | `session_id`, `charger_id`, `start_ts`, `end_ts`?, `energy_kwh`, `cost`, `price_samples: [{ts, kwh, price}]` (only in `completed`), `soc_start`?, `soc_end`? |
| `charge.soc_update` | `session_id`, `soc_start`?, `soc_end`?. Sent later, once the cloud car has reported its battery level. |
| `external_charge.detected` | `window_start`, `window_end`, `place`, `battery_start_pct`, `battery_end_pct`, `energy_kwh_estimated`, `car_reported_charging`, `flags: [...]` |
| `refuel.detected` | `ts`, `place`, `odometer`, `fuel_start_l`, `fuel_end_l`, `litres_estimated`, `suggested_price_per_l`, `price_source` |
| `idle.recorded` | `start_ts`, `end_ts`, `battery_delta_pct`, `energy_kwh`, `fuel_l` |
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
| `/trips` | M3 | `POST /trips/{id}/split {at_km, at_ts}`, `POST /trips/merge {ids:[a,b]}` |
| `/charges` | M2 | Includes home, public and manual sessions. Filter `?kind=home\|public\|manual`. |
| `/refuels` | M1 | List items include `interval_km` and `l_per_100km` on refuels that close a full-to-full interval |
| `/odometer-readings` | M1 | |
| `/maintenance` | M1 | Maintenance records (attachments from M5) |
| `/maintenance-schedules` | M4 | `GET /maintenance-schedules/due?vehicle_id=` gives next due per schedule |
| `/expenses` | M1 | One-off and recurring |
| `/attachments` | M5 | `POST` multipart upload. Returns an id to link from records. |
| `/review-items` | M2 | `POST /review-items/{id}/resolve {action, values}` |

## Derived data

| Method | Path | Purpose |
|---|---|---|
| GET | `/summary?vehicle_id=&from=&to=&months=12` | **M1.** Per vehicle and combined: totals for the period, the last 12 months, a monthly series, latest odometer and last refuel. From M2 also last trip, next maintenance, review count and open sessions. |
| GET | `/reports/period?vehicle_id=&from=&to=&group=month` | Totals per group and category |
| GET | `/reports/compare?vehicle_ids=a,b&from=&to=` | Side-by-side metrics |
| GET | `/records/{id}/explain` | Cost breakdown of one record: inputs, prices used, cost basis at that moment |
| POST | `/ledger/recalculate?vehicle_id=&from=` | Forces a recalculation. This is normally automatic. |

## Export and backup

| Method | Path | Purpose |
|---|---|---|
| GET | `/export/{resource}.csv` | **M1.** Same filters as the list endpoint. `.xlsx` follows in M4. |
| GET | `/backup` | Full JSON dump, including attachments as base64 when `?attachments=true` |
| POST | `/restore` | Restores a backup into an **empty** database, or with `?mode=merge` (matched by id) |
| POST | `/import/csv` | Multipart file plus a column mapping. Returns a preview first, and commits with `?commit=true`. |
