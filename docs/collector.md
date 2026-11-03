# AutoLedger Collector (custom integration)

Domain: `autoledger`. Installed through HACS. It turns the states of your car and charger entities into records and delivers them to the AutoLedger add-on.

> **Built in M2 and M3:** setup (discovery + manual), vehicle and charger subentries, snapshots, home charge sessions, public charge and refuel detection, odometer readings, trips (snapshot mode), idle consumption, backfill, the outbox, the sensors, the services and the events. Marked *(M5)* below: live trip mode, snapshot boost and the remaining services.

## Setup

1. Install and start the **AutoLedger add-on** first ([addon.md](addon.md#installation)).
2. Install **AutoLedger Collector** via HACS and restart HA.
3. HA shows *"AutoLedger discovered"*. Click **Configure**. Without discovery, add the integration manually and enter the URL and token from the add-on's Settings page.
4. On the integration page, use **Add vehicle**. This is a config subentry, and you add one per connected car:
   1. Pick the add-on vehicle to link to, or create a new one. The add-on vehicle holds the name, plate, battery capacity and tank size.
   2. Pick a **profile**: `PHEV`, `BEV` or `ICE`. The profile decides which entity roles are offered.
   3. Map the entities (see the table below). The flow pre-fills suggestions when all entities belong to one device, using the entity names a vehicle integration typically uses.
5. Optional: **Add charger**, also a subentry, once per home charger. Map its kWh counter and assign it to a vehicle.

Every setting can be changed later through the subentry's **Reconfigure** option. Options are stored where they are read, so no setting is ever silently ignored.

## Entity roles

### Vehicle subentry

| Role | Required | Expected entity | Used for |
|---|---|---|---|
| `odometer` | **yes** | sensor, km (or mi, converted) | Trip distance (fallback), odometer readings |
| `trip_meter` | no | sensor, km with 0.1 km resolution, may reset | More precise trip distance |
| `battery_level` | PHEV/BEV | sensor, % | kWh used per trip, external charge detection |
| `fuel_level` | PHEV/ICE | sensor, **litres or %** (the unit is chosen in the flow) | Litres used, refuel detection |
| `location` | no | `device_tracker` with latitude/longitude attributes, **or** a pair of latitude/longitude sensors | Start and end points, zones |
| `address` | no | sensor with a readable address | Trip labels ("Duinmeierij 118 → Albert Heijn") |
| `charging_state` | no | sensor or binary_sensor | Telling charging apart from noise, public charge confirmation |
| `plug_state` | no | sensor or binary_sensor (connected/disconnected) | Charge-session vehicle attribution |
| `car_timestamp` | no | sensor containing the car's own report time | Exact event times for cloud-based cars |
| `days_to_service`, `distance_to_service` | no | sensors with the car's own service countdown (Lynk: `…_days_to_service`, `…_distance_to_service`) | Shown next to the maintenance schedules as a cross-check. Read at every snapshot and sent as `service.status` when they change; they do not trigger a snapshot. |
| `fuel_flap`, `running`, `fuel_price` | *(M5)* | | Refuel confirmation, live trip mode, refuel price suggestion. Until then the add-on suggests the price of your last refuel, or the default from Settings. |

The vehicle's type, tank size, usable battery and wall kWh per % come from the add-on. The Collector takes them over again on every summary poll (5 min), so a change on the add-on's Vehicles page needs no reconfigure or reload. The latest values are kept in the Collector's store and used after a restart, even when the add-on is not reachable yet.

### Charger subentry

| Role | Required | Expected entity | Used for |
|---|---|---|---|
| `energy` | **yes** | sensor, kWh, `total_increasing` | Charge-session energy. This is the **only** source of kWh. |
| `power` | no | sensor, W or kW | Session start and stop detection, live power on the GUI |
| `switch` | no | switch | Session end hint, shown in the GUI |
| `price` | no | sensor, €/kWh (dynamic or fixed tariff) | Pricing each kWh at the moment it is delivered |
| `vehicle` | no | one of the vehicle subentries | Which car gets the session, and whose battery rise it explains. Without one, sessions land in the review inbox, and that car's battery rise from a home charge is reported as a public charge. *Auto (by plug state)* follows later. Add the vehicle before the charger, or pick it afterwards with *Change charger*. |

## Snapshots

Each vehicle has one snapshot builder. It listens to state changes of the car's mapped entities and waits until 30 s have passed without another change. Then it reads every value at once into a **Snapshot**. The home charger's counter is *read* at that moment but does not *trigger* snapshots, so its change between two car reports is exactly the home energy in that window:

```
Snapshot
  ts             car timestamp if mapped and valid, else HA time of the last change
  odometer_km    trip_meter_km  battery_pct  fuel_l
  lat  lon  address  zone        (zone = HA zone containing lat/lon, e.g. "home")
  charging  plugged  fuel_flap_open
  charger_kwh    (counter of the assigned home charger at that moment)
```

- Values that are `unavailable`, `unknown`, non-numeric or physically impossible are taken from the previous snapshot and marked *stale*. Impossible values include an odometer going down, a battery above 100 %, or fuel above the tank size plus 10 %.
- A snapshot that changed nothing relevant is dropped.
- The last **committed** snapshot is persisted in the Store. Detectors always compare *new snapshot* against *last committed snapshot*. This delta-based design is why restarts and sparse data are handled correctly.

## Trip detection

### Snapshot mode (default, and correct for cloud cars like the Lynk)

Many connected cars upload their state only when they park or wake up, and the integration polls that cloud periodically. HA therefore sees a few snapshots per day, not a live stream. One snapshot can sum up several drives.

A **trip** is created when two consecutive snapshots differ by at least `min_trip_km` (default 0.5 km):

| Field | How |
|---|---|
| `start_ts` | The time the car was last seen parked (the previous snapshot). Flagged `estimated`, because the car may have stood still for a while after that. *(M5: refine it with an average speed.)* |
| `end_ts` | The new snapshot's `ts` |
| `start_*` / `end_*` place | lat/lon, address and zone of the previous and new snapshot |
| `distance_km` | `Δtrip_meter` when it agrees with the odometer (Δodometer − 1 ≤ Δtrip ≤ Δodometer + 1, so no reset and no lagging trip meter); otherwise `Δodometer` |
| `battery_*`, `charged_kwh` | Battery % at both ends, plus the kWh charged within the same window: the home charger's counter delta, or the estimate of a detected public charge. The **add-on** turns this into energy: `(start − end) × kwh_per_pct + charged_kwh` (see [costs.md](costs.md#kwh-per-percent)). A negative result means the engine charged the battery on a PHEV. |
| `fuel_*` | Tank level at both ends. The add-on smooths these levels between refuels and takes the drop of the smoothed level as provisional litres, because fuel level sensors are noisy (see [costs.md](costs.md#fuel-gauge-noise)). |
| `kind` | `round_trip` when start and end are within 150 m or in the same zone, otherwise `one_way` |
| `flags` | `refuel_in_window`, `charge_in_window` |

If the same segment *also* shows the battery going up or the fuel going up, the trip is still created. The extra energy becomes a separate external-charge or refuel event, flagged for review (see below). One report can cover several drives; split such a trip on the Trips page.

### Live mode *(M5)* (optional, for cars with a live `running` sensor)

When `running` is mapped *and* reports live (it changes while the car is actually driving), a trip opens when `running` turns on and closes when it has been off for `trip_end_delay` (default 3 min). Snapshots in between update the open trip. Two trips less than `merge_gap` apart (default 2 min) are merged.

The flow only offers live mode after it has seen `running` change at least once. Otherwise a cloud car would fall back to empty trips.

### Snapshot boost *(M5)* (optional, off by default)

For cars whose integration offers a "refresh now" service (for example `lynkco.force_update_data`), the collector can call it a few times after it notices a hint that a drive started or ended. Hints are the lock changing, the plug disconnecting, or `running` changing. This gives better start and end points.

The trade-off is extra cloud calls and possibly waking the car, so it is limited to `boost_max_per_day` (default 12).

## Home charge detection

Each charger subentry runs a small state machine:

```
IDLE ──(energy counter rises ≥ 0.05 kWh, or power > start_w for 60 s)──► CHARGING
CHARGING ──(power < stop_w, or counter flat, for 10 min)──► FINALISING
FINALISING ──(no increase for another 5 min)──► IDLE   → emit charge.completed
FINALISING ──(counter rises again)──► CHARGING           (same session, e.g. a timer pause)
```

- **Energy comes only from the cumulative kWh counter**, never from integrating power. A sensor dropping to `unavailable` does nothing. The next valid counter value covers the gap.
- **Pricing per increment.** Every time the counter rises by Δ kWh, `cost += Δ × price_now`, using the `price` entity's current state, or the fixed price when that is unavailable. A night charge on a dynamic tariff is therefore priced correctly hour by hour. The session stores both `energy_kwh` and `cost`, plus the effective average €/kWh.
- **Vehicle attribution.** The session goes to the charger's assigned vehicle. In *auto* mode it goes to the vehicle whose `plug_state` is connected. If no vehicle claims it, the session is still recorded and lands in the review inbox.
- **Battery %.** `soc_start` and `soc_end` are filled in from the vehicle's snapshots nearest to the session's start and end, taken up to 6 h after the end because cloud cars report late. These values feed the [kWh-per-% learning](costs.md#kwh-per-percent).
- **Persistence.** The open session, its last counter value and its running cost are written to the Store on every increment. `charge.updated` events go out every 15 min.
- Sessions below `min_session_kwh` (default 0.2) are discarded, since those are standby blips.

## External (public) charge detection

This applies to PHEV and BEV. Between two snapshots, an external charge is assumed when:

- `Δbattery_pct ≥ +3 %` (configurable), **and**
- the assigned home charger delivered `< 0.2 kWh` in that window.

The event carries `energy_kwh_estimated = Δbattery_pct × kwh_per_pct`, the place and the time window. Its status is `needs_price`, so it appears in the review inbox, where you enter the price per kWh or the total amount. The default comes from the add-on setting *public charging price*.

If `charging_state` is mapped, the event also records whether the car itself reported charging. When it did not, and the segment includes driving, the event is flagged `possible_engine_charge`: a PHEV can charge its battery from the engine.

## Refuel detection

This applies to PHEV and ICE. Between two snapshots, a refuel is assumed when `Δfuel_l ≥ refuel_min_l` (default 3 L), or when `fuel_flap` opened and closed and `Δfuel_l > 1 L`.

- `litres = Δfuel_l`. If the segment also contains driving, the litres used on the way are estimated from the vehicle's recent L/100 km and added. The value is marked `estimated`, because the receipt is the truth.
- `price_per_l` comes from the `fuel_price` entity, or else from the last refuel's price. Status: `needs_review`.
- The place is the end point of the segment, the address being the fuel station's.
- The collector fires `autoledger_refuel_detected` so an automation can ask you for the receipt amount right away (example below).

## Idle consumption

When the battery or fuel drops between snapshots **without** distance (pre-climate, standby, cabin heating while parked), an `idle` record is emitted, as long as the drop exceeds the noise threshold (default 1 % or 0.5 L) and the home charger delivered nothing in that window. It is costed like a trip but reported separately as *"climate & standby"*, so the €/km of real driving is not distorted.

## Odometer readings

Every snapshot in which the odometer changed sends an `odometer.reading`. This gives the add-on a continuous odometer history, so km per month are known for a connected car before its first trip, and also for distance the trip detector would miss (for example while HA was down for days).

## Backfill

Service `autoledger.backfill` takes a `vehicle` and a `start` date. It reads the recorder history of the mapped entities from that date **up to the moment live tracking began** and replays it through the detectors, one snapshot per burst of changes as in live mode. Use it right after installing, to recover the last days (the HA recorder keeps about 10 days by default).

- Backfilled events get UUIDs derived from vehicle, type and time, so running backfill twice creates nothing twice.
- It stops where live tracking began, so nothing is detected twice. Gaps *after* that (HA down for days) are covered by the odometer readings; their km count, but no trips are made for them.
- Trips, idle records, refuels, public charges and odometer readings are backfilled. Home charge sessions are not: add those by hand on the Charging page if needed.
- The response tells how many snapshots and events it found.

## Delivery (outbox)

- Events are appended to the persisted outbox, then sent in batches of up to 100 to `POST /api/v1/ingest`.
- When delivery fails, retries back off: 10 s, 30 s, 2 min, 10 min, then every 10 min.
- The outbox is capped at 10 000 events, about a year of data. When the cap is reached, the oldest `charge.updated` progress events are dropped first, never completed records.
- Repair issues are raised when the add-on is unreachable for 24 h, when the add-on API version is incompatible, or when a required entity has been unavailable for 7 days.

## Exposed entities

One HA **device** per add-on vehicle (manual vehicles such as the VW Up included) and one per charger. Vehicle values come from the add-on summary, which is polled every 5 minutes and right after each delivery. Charger values are live from the collector:

| Entity | Unit | Notes |
|---|---|---|
| `sensor.<car>_cost_this_month` | EUR | device_class `monetary`, state_class `total`. Energy costs plus maintenance plus expenses. |
| `sensor.<car>_energy_cost_this_month` | EUR | Electricity and fuel only |
| `sensor.<car>_energy_cost_per_km` | EUR/km | Rolling 12 months, energy only. No device class. |
| `sensor.<car>_total_cost_per_km` | EUR/km | Rolling 12 months, everything included |
| `sensor.<car>_distance_this_month` | km | device_class `distance` |
| `sensor.<car>_electricity_this_month` | kWh | device_class `energy`, state_class `total` |
| `sensor.<car>_fuel_this_month` | L | device_class `volume` |
| `sensor.<car>_fuel_consumption` | L/100 km | Rolling 12 months, full-to-full |
| `sensor.<car>_last_charge` | kWh | Attributes: start, end, cost, average price, kind |
| `sensor.<car>_odometer` | km | Latest known odometer |
| `sensor.autoledger_items_to_review` | count | Number of items in the review inbox |
| `binary_sensor.<charger>_charging` | — | A session is running (collector state, live) |
| `sensor.<charger>_session_energy` / `_session_cost` | kWh / EUR | Live values of the open session |
| `sensor.<car>_last_trip` | km | Attributes: start, end, from, to, kWh, L, cost |
| `sensor.<car>_electric_consumption` | kWh/100 km | Rolling 12 months, trips only. Attribute `electric_share` (PHEV). |
| `sensor.<car>_next_maintenance` | d | device_class `duration`. Days to the most urgent active schedule (negative when overdue). Attributes: `name`, `status`, `due_date`, `due_km`, `km_left`, `estimated_date`, `reason`, `schedules`, and the car's own `car_days_to_service` / `car_distance_to_service`. |
| `binary_sensor.<car>_maintenance_due` | — | device_class `problem`. On while a schedule is due soon or overdue. Attribute `items`. |

## Services

The `vehicle` field is a device selector filtered to AutoLedger vehicles, so there is no free-text ID. All services forward to the add-on API, and they work for **manual** vehicles too: the add-on's manual vehicles are created as devices as well.

| Service | Fields |
|---|---|
| `autoledger.add_refuel` | `vehicle`, `litres`, `total_cost` **or** `price_per_l`, `odometer`?, `full_tank` (default true), `station`?, `timestamp`? |
| `autoledger.add_charge` | `vehicle`, `energy_kwh`, `total_cost` **or** `price_per_kwh`, `location`?, `timestamp`? |
| `autoledger.add_odometer` | `vehicle`, `odometer`, `timestamp`? |
| `autoledger.backfill` | `vehicle`, `start` (date). Returns `{from, until, snapshots, events}`. See [Backfill](#backfill). |
| `autoledger.resync` | Resends the outbox and refreshes the summary |
| *(later)* `add_maintenance`, `add_expense`, `end_trip` | |

The `add_*` services return the new record's `id` as a service response.

## Events

| Event | Data |
|---|---|
| `autoledger_charge_completed` | `vehicle_id`, `record_id`, `energy_kwh`, `cost` |
| `autoledger_refuel_detected` | `vehicle_id`, `record_id`, `litres` |
| `autoledger_review_needed` | `vehicle_id`, `record_id`, `reason` (`refuel_price`, `public_charge_price`), `energy_kwh` for charges |
| `autoledger_trip_recorded` | `vehicle_id`, `record_id`, `distance_km`, `start_ts`, `end_ts`, `kind` |
| `autoledger_maintenance_due` | `vehicle_id`, `vehicle_name`, `schedule_id`, `name`, `status` (`soon`/`overdue`), `due_date`, `due_km`, `km_left`, `estimated_date`, `days_left`, `reason` |

Events fire once the add-on has stored the record, so `record_id` is always valid. `autoledger_maintenance_due` fires from the summary poll: once when a schedule becomes due soon, and once more when it becomes overdue. After it is done, the next cycle is announced again. What was announced is kept in the Collector's store, so a restart does not repeat it.

Example: ask for the receipt after a refuel.

```yaml
triggers:
  - trigger: event
    event_type: autoledger_refuel_detected
actions:
  - action: notify.mobile_app_phone
    data:
      title: "Refuel detected"
      message: "{{ trigger.event.data.litres }} L added. Open AutoLedger → Review to enter the amount you paid."
```

## Options (per vehicle subentry)

| Option | Default | Meaning |
|---|---|---|
| `min_trip_km` | 0.5 | Smaller distance deltas count as GPS/odometer noise |
| `trip_mode` *(M5)* | `snapshot` | `snapshot` or `live` |
| `trip_end_delay` *(M5)* | 3 min | Live mode only |
| `external_charge_min_pct` | 3 % | Threshold for detecting a public charge |
| `refuel_min_l` | 3 L | Threshold for detecting a refuel |
| `idle_min_pct` / `idle_min_l` | 1 % / 0.5 L | Thresholds for idle-consumption records |
| `boost_service`, `boost_max_per_day` *(M5)* | — / 12 | Optional "refresh now" service |

Charger subentry options: `start_w` (default 500), `stop_w` (default 100), `min_session_kwh` (default 0.2), and `fixed_price`, which is used when no price entity is mapped or it is unavailable. When neither is available, the add-on's fallback electricity price is used. The price source is stored with every price sample.

## Diagnostics

The HA diagnostics download contains, with location redacted: the entity mapping, the last committed snapshot, open sessions, the outbox length and its oldest entry, the last 50 detector decisions with their reasons ("segment 63439→63445 km: trip 6.3 km, battery −11.5 %, fuel −0.4 L"), and the add-on version.
