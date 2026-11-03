# Data model

The add-on stores its data in SQLite at `/data/autoledger.db`. Migrations are managed with Alembic.

## Conventions

Every table has these columns:

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | UUIDv7 |
| `created_at`, `updated_at` | TEXT | ISO 8601 UTC |
| `version` | INTEGER | Optimistic locking, incremented on every update |
| `deleted_at` | TEXT NULL | Soft delete |

Records that can be created automatically also have:

| Column | Type | Notes |
|---|---|---|
| `source` | TEXT | `collector`, `manual`, `import` or `backfill` |
| `status` | TEXT | `ok`, `estimated`, `needs_review` or `provisional` |
| `locked_fields` | JSON | Field names the user edited. Collector updates never overwrite them. |
| `auto_values` | JSON | Original collector values of the locked fields, shown as *auto* in the GUI |
| `ingest_uuid` | TEXT NULL | The event that created the record |

Money (in the currency from Settings) and quantities are stored as `REAL`. Derived values are rounded on calculation (litres 3 decimals, prices 4, totals 2), and figures are rounded again for display. Timestamps are fixed-width UTC strings (`2026-11-02T12:42:56.941000Z`), so sorting the text sorts by time.

Tables built in **M1**: `vehicles`, `refuels`, `odometer_readings`, `maintenance_records`, `expenses` and `settings`. Added in **M2** (migration 0002): `charge_sessions`, `review_items`, `ingest_events`, plus `vehicles.kwh_per_pct`. The other tables arrive with their milestone, each through its own Alembic migration.

## Tables

### `vehicles`
`name`, `plate`, `make`, `model`, `year`, `type` (`ICE`/`PHEV`/`BEV`), `fuel_type`, `tank_l`, `battery_usable_kwh`, `tracking` (`collector`/`manual`), `start_odometer_km`, `start_date`, `start_battery_value`, `start_tank_value`, `purchase_price`, `purchase_date`, `resale_estimate`, `resale_date`, `depreciation_enabled`, `color`, `icon`, `archived_at`

### `trips`
`vehicle_id`, `start_ts`, `start_ts_estimated`, `end_ts`, `start_lat`, `start_lon`, `start_address`, `start_zone`, `end_lat`, `end_lon`, `end_address`, `end_zone`, `kind` (`one_way`/`round_trip`), `odometer_start`, `odometer_end`, `distance_km`, `distance_source` (`trip_meter`/`odometer`/`manual`), `battery_start_pct`, `battery_end_pct`, `battery_used_pct` (start − end; summed when merged), `charged_kwh` (charged within the window), `energy_kwh` (only when set by hand), `fuel_start_l`, `fuel_end_l`, `fuel_l` (raw drop of the gauge), `origin` (JSON: `merged_from` or `split_from`), `note`. Energy, reconciled litres and cost are derived by the ledger, not stored.

### `idle_records`
`vehicle_id`, `start_ts`, `end_ts`, `zone`, `battery_start_pct`, `battery_end_pct`, `battery_used_pct`, `energy_kwh` (only when set by hand), `fuel_l`, `note`; the tank levels are kept in `auto_values`

### `charge_sessions`
`vehicle_id` (NULL until assigned), `session_key` (the collector's `session_id`, unique), `kind` (`home`/`public`/`manual`), `charger_key`, `charger_name`, `start_ts`, `end_ts`, `is_open`, `lat`, `lon`, `address`, `provider`, `energy_kwh`, `energy_estimated`, `soc_start`, `soc_end`, `price_mode` (`samples`/`per_kwh`/`total`/`free`), `price_per_kwh`, `price_total`, `session_fee`, `auto_cost` (the collector's), `cost` (effective), `price_samples` (JSON: ts, kWh, price, source), `note`

### `refuels`
`vehicle_id`, `ts`, `odometer_km`, `litres`, `price_per_l`, `total`, `full_tank`, `station`, `lat`, `lon`, `fuel_type`, `attachment_id`

### `odometer_readings`
`vehicle_id`, `ts`, `odometer_km`. Unique on (`vehicle_id`, `ts`).

### `maintenance_records`
`vehicle_id`, `date`, `odometer_km`, `category`, `description`, `garage`, `cost`, `schedule_id` (NULL), `attachments` (JSON list of ids)

### `maintenance_schedules`
`vehicle_id`, `name`, `category`, `interval_months`, `interval_km`, `last_done_date`, `last_done_km`, `remind_before_days`, `remind_before_km`, `active`

### `expenses`
`vehicle_id`, `category`, `amount`, `date` (one-off) **or** `recurrence` (`monthly`/`quarterly`/`yearly`) with `start_date` and `end_date`, `note`, `attachment_id`

### `attachments`
`filename`, `mime_type`, `size`, `path` (under `/data/attachments/`), `sha256`

### `review_items`
`vehicle_id`, `record_type`, `record_id`, `reason`, `details` (JSON), `resolved_at`, `resolution` (JSON)

### `ingest_events`
`uuid` (primary key), `type`, `vehicle_id`, `occurred_at`, `received_at`, `payload` (JSON), `result` (`applied`/`rejected`), `record_id`, `error`. This is the audit log, kept for 1 year by default.

### `ledger_states` *(not built)*
A cache of the replay states per record. Not needed yet: costs are recalculated on every request (see [costs.md](costs.md#recalculation)).

### `efficiency_factors` *(not built)*
Not needed: the learned factor at any moment follows from the home sessions finished before it, and the manual value is the vehicle's `kwh_per_pct` (see [costs.md](costs.md#kwh-per-percent)).

### `settings`
`key`, `value` (JSON)

## Relationships

```
vehicles 1─* trips, idle_records, charge_sessions, refuels, odometer_readings,
             maintenance_records, maintenance_schedules, expenses, efficiency_factors, ledger_states
maintenance_schedules 1─* maintenance_records
attachments *─ refuels, maintenance_records, expenses
review_items ─ any record (record_type + record_id)
```
