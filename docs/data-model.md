# Data model

The add-on stores its data in SQLite at `/data/autoledger.db`. Migrations are managed with Alembic. Attachment files are kept in `/data/attachments/`, and the API token in `/data/secret.json`.

## Conventions

Every table except `ingest_events` and `settings` has these columns:

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | UUIDv7 |
| `created_at`, `updated_at` | TEXT | ISO 8601 UTC |
| `version` | INTEGER | Optimistic locking, incremented on every update |
| `deleted_at` | TEXT NULL | Soft delete |

Records that can be created automatically (`trips`, `idle_records`, `charge_sessions`, `refuels`, `odometer_readings`) also have:

| Column | Type | Notes |
|---|---|---|
| `source` | TEXT | `collector`, `manual` or `import` |
| `status` | TEXT | `ok` or `needs_review` |
| `locked_fields` | JSON | Field names the user edited. Collector updates never overwrite them. |
| `auto_values` | JSON | Original collector values of the locked fields, plus extra collector data such as tank levels |
| `ingest_uuid` | TEXT NULL | The event that created the record (unique) |

Money (in the currency from Settings) and quantities are stored as `REAL`. Derived values are rounded on calculation (litres 3 decimals, prices 4, totals 2), and figures are rounded again for display. Timestamps are fixed-width UTC strings (`2026-11-02T12:42:56.941000Z`), so sorting the text sorts by time.

The schema is built by migrations 0001 (vehicles, refuels, odometer readings, maintenance, expenses, settings) to 0005 (attachments and depreciation).

## Tables

### `vehicles`
`name`, `plate`, `make`, `model`, `year`, `type` (`ICE`/`PHEV`/`BEV`), `fuel_type` (`petrol`/`diesel`/`lpg`, `none` for a BEV), `tank_l`, `battery_usable_kwh`, `kwh_per_pct` (wall kWh per battery %; NULL: derived from the capacity), `tracking` (`collector`/`manual`, default `manual`; set to `collector` when the Collector delivers data for the vehicle), `start_odometer_km`, `start_date`, `purchase_price`, `purchase_date`, `resale_estimate`, `resale_date`, `depreciation_enabled` (default false), `color`, `note`, `archived_at`

### `trips`
`vehicle_id`, `start_ts`, `start_ts_estimated`, `end_ts`, `start_lat`, `start_lon`, `start_address`, `start_zone`, `end_lat`, `end_lon`, `end_address`, `end_zone`, `kind` (`one_way`/`round_trip`), `odometer_start`, `odometer_end`, `distance_km`, `distance_source` (`trip_meter`/`odometer`/`manual`), `battery_start_pct`, `battery_end_pct`, `battery_used_pct` (start − end; summed when merged), `charged_kwh` (charged within the window), `energy_kwh` (only when set by hand), `fuel_start_l`, `fuel_end_l`, `fuel_l` (raw drop of the gauge), `origin` (JSON: `merged_from` or `split_from`), `note`. Energy, reconciled litres and cost are derived by the ledger, not stored.

### `idle_records`
`vehicle_id`, `start_ts`, `end_ts`, `zone`, `battery_start_pct`, `battery_end_pct`, `battery_used_pct`, `energy_kwh` (only when set by hand), `fuel_l`, `note`; the tank levels are kept in `auto_values`

### `charge_sessions`
`vehicle_id` (NULL until assigned), `session_key` (the collector's `session_id`, unique), `kind` (`home`/`public`/`manual`), `charger_key`, `charger_name`, `start_ts`, `end_ts`, `is_open`, `lat`, `lon`, `address`, `provider`, `energy_kwh`, `energy_estimated`, `soc_start`, `soc_end`, `price_mode` (`samples`/`per_kwh`/`total`/`free`), `price_per_kwh`, `price_total`, `session_fee`, `auto_cost` (the collector's), `cost` (effective), `price_samples` (JSON: ts, kWh, price, source), `note`

### `refuels`
`vehicle_id`, `ts`, `odometer_km`, `litres`, `price_per_l`, `total`, `full_tank`, `station`, `note`. Receipts are in `attachments`.

### `odometer_readings`
`vehicle_id`, `ts`, `odometer_km`, `note`. Indexed on (`vehicle_id`, `ts`); the collector skips a reading with the same time.

### `maintenance_records`
`vehicle_id`, `date`, `odometer_km`, `category` (`service`/`inspection`/`tyres`/`repair`/`battery`/`cleaning`/`other`), `description`, `garage`, `cost`, `schedule_id` (NULL: counts for the schedules of its category), `note`. Invoices are in `attachments`.

### `maintenance_schedules`
`vehicle_id`, `name`, `category`, `interval_months`, `interval_km`, `last_done_date`, `last_done_km`, `remind_before_days` (30), `remind_before_km` (1000), `active`, `note`. `last_done_*` is the starting point you enter; newer maintenance records of the schedule move it forward when it is read, so nothing derived is stored. The car's own service countdown (`service.status`) is kept in `settings` under `car_service:<vehicle_id>`.

### `expenses`
`vehicle_id`, `category` (`insurance`/`road_tax`/`parking`/`tolls`/`car_wash`/`fine`/`accessories`/`lease`/`subscription`/`other`), `amount`, `date` (the start date when recurring), `recurrence` (NULL for one-off, or `monthly`/`quarterly`/`yearly`), `end_date` (recurring only), `note`. Receipts are in `attachments`.

### `attachments`
`resource` (`refuels`/`maintenance`/`expenses`), `record_id`, `filename`, `mime_type`, `size`, `sha256`. The file is `/data/attachments/<id>`. A record can have several. Deleting one is a soft delete; the file stays.

### `review_items`
`vehicle_id`, `record_type` (`refuel`/`charge`), `record_id`, `reason` (`refuel_price`, `public_charge_price`, `possible_engine_charge`, `charge_without_vehicle` or `rejected_event`), `details` (JSON), `resolved_at`, `resolution` (JSON)

### `ingest_events`
`uuid` (primary key), `type`, `vehicle_id`, `occurred_at`, `received_at`, `payload` (JSON), `result` (`applied`/`rejected`), `record_id`, `error`. This is the audit log of collector events.

### `settings`
`key` (primary key), `value` (JSON). The settings from the GUI are under `general`.

## Relationships

```
vehicles 1─* trips, idle_records, charge_sessions, refuels, odometer_readings,
             maintenance_records, maintenance_schedules, expenses, review_items
maintenance_schedules 1─* maintenance_records
attachments *─ refuels, maintenance_records, expenses (resource + record_id)
review_items ─ refuels, charge_sessions (record_type + record_id)
```
