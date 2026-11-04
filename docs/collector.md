# AutoLedger Collector (custom integration)

Domain: `autoledger`. Installed through HACS. It turns the states of your car and charger entities into records and delivers them to the AutoLedger add-on.

## Setup

The integration ships its own icon in `custom_components/autoledger/brand/` (`icon.png`, `icon@2x.png`), which Home Assistant 2026.3 and later shows without a brands-repository entry. The add-on's `icon.png` and `logo.png` are rendered from the same source, `assets/icon.svg`.

The Collector comes in English and Dutch (`translations/en.json`, `translations/nl.json`). The setup and service screens follow the language of your HA user profile; entity names follow the language of the HA installation when the entities are created.

1. Install and start the **AutoLedger add-on** first ([addon.md](addon.md#installation)).
2. Install **AutoLedger Collector** via HACS and restart HA.
3. HA shows the discovered *AutoLedger* add-on. Click **Configure** and confirm. Without discovery, add the integration manually: the URL is suggested from your installed add-ons, and the token is on the add-on's Settings page.
4. On the integration page, use **Add vehicle**. This is a config subentry, and you add one per connected car:
   1. Pick the add-on vehicle to link to, and its odometer sensor. The vehicle must exist in the add-on first; it holds the name, type (`PHEV`, `BEV` or `ICE`), plate, battery capacity and tank size. The type decides which entity roles are offered.
   2. Map the other entities (see the table below). The flow suggests them from the odometer's device, using the entity id endings vehicle integrations typically use.
5. Optional: **Add home charger**, also a subentry, once per home charger. Map its kWh counter and assign it to a vehicle.

A vehicle's mapping is changed with **Change entities**, a charger's with **Change charger**, and the connection with the integration's **Reconfigure**. When the add-on refuses the token (for example after it was regenerated), HA asks for the new one.

## Entity roles

### Vehicle subentry

| Role | Required | Expected entity | Used for |
|---|---|---|---|
| `odometer` | **yes** | sensor, km (or mi, converted) | Trip distance (fallback), odometer readings |
| `trip_meter` | no | sensor, km with 0.1 km resolution, may reset (mi converted) | More precise trip distance |
| `battery_level` | PHEV/BEV | sensor, % | kWh used per trip, public charge and idle detection |
| `fuel_level` | PHEV/ICE | sensor, **litres or %** (the unit is chosen in the flow; % is converted with the add-on's tank size) | Litres used, refuel and idle detection |
| `tracker` | no | `device_tracker` with latitude/longitude attributes | Start and end points, zones |
| `latitude`, `longitude` | no | a pair of sensors, used when there is no device tracker | Start and end points, zones |
| `address` | no | sensor with a readable address | Trip labels ("Duinmeierij 118 → Albert Heijn"), the station of a detected refuel |
| `charging_state` | PHEV/BEV, no | sensor or binary_sensor | Whether the car itself reported charging during a detected public charge |
| `car_timestamp` | no | sensor containing the car's own report time | Exact event times for cloud-based cars |
| `days_to_service`, `distance_to_service` | no | sensors with the car's own service countdown (Lynk: `…_days_to_service`, `…_distance_to_service`) | Shown next to the maintenance schedules as a cross-check. Read at every snapshot and sent as `service.status` when they change; they do not trigger a snapshot. |
| `fuel_price` | PHEV/ICE, no | sensor or input_number in €/L (for example from a fuel price integration) | Read when a refuel is detected: its state becomes the suggested price (`price_source: entity`). Values outside 0.30–10 €/L are ignored. Without it, the add-on suggests the price of your last refuel, or the default for the vehicle's fuel type from Settings. |

The vehicle's type, tank size, usable battery and wall kWh per % come from the add-on. The Collector takes them over again on every summary poll (5 min), so a change on the add-on's Vehicles page needs no reconfigure or reload. The latest values are kept in the Collector's store and used after a restart, even when the add-on is not reachable yet.

### Charger subentry

| Role | Required | Expected entity | Used for |
|---|---|---|---|
| `name` | **yes** | text (default *Home charger*) | Device name and the charger name on sessions |
| `energy` | **yes** | sensor, kWh, cumulative (device class `energy`) | Charge-session energy. This is the **only** source of kWh. |
| `power` | no | sensor, W or kW | Noticing the end of a session sooner |
| `switch` | no | switch | Turning it off counts as power 0, a session end hint |
| `price` | no | sensor, €/kWh (dynamic or fixed tariff) | Pricing each kWh at the moment it is delivered |
| `vehicle` | no | one of the vehicle subentries | Which car gets the session, and whose battery rise it explains. Without one, sessions land in the review inbox, and that car's battery rise from a home charge is reported as a public charge. Add the vehicle before the charger, or pick it afterwards with *Change charger*. |

## Snapshots

Each vehicle has one snapshot builder. It listens to state changes of the car's mapped entities and waits until 30 s have passed without another change. Then it reads every value at once into a **Snapshot**. The home charger's counter is *read* at that moment but does not *trigger* snapshots, so its change between two car reports is exactly the home energy in that window:

```
Snapshot
  ts             car timestamp if mapped and valid, else HA time when the snapshot is taken
  odometer_km    trip_meter_km  battery_pct  fuel_l
  lat  lon  address  zone        (zone = HA zone containing lat/lon, e.g. "home")
  charging  plugged
  charger_kwh    (sum of the counters of the home chargers assigned to the car)
```

- The car timestamp is valid when it is at most 5 min in the future and later than the previous snapshot's.
- Values that are `unavailable`, `unknown` or non-numeric are taken from the previous snapshot. So are physically impossible values: an odometer going down, a battery outside 0–100 %, or fuel below 0 or above the tank size plus 10 %. Each replacement of an impossible value is logged in the diagnostics' decisions.
- A snapshot that differs from the previous one only in its time is dropped.
- The first snapshot after setup is stored as the baseline. The last **committed** snapshot is persisted in the Store. Detectors always compare *new snapshot* against *last committed snapshot*. This delta-based design is why restarts and sparse data are handled correctly.

## Trip detection

### Snapshot mode

Many connected cars upload their state only when they park or wake up, and the integration polls that cloud periodically. HA therefore sees a few snapshots per day, not a live stream. One snapshot can sum up several drives, so trips are detected per segment between two snapshots.

A **trip** is created when the odometer of two consecutive snapshots differs by at least `min_trip_km` (default 0.5 km):

| Field | How |
|---|---|
| `start_ts` | The time the car was last seen parked (the previous snapshot). Flagged `estimated`, because the car may have stood still for a while after that. |
| `end_ts` | The new snapshot's `ts` |
| `start_*` / `end_*` place | lat/lon, address and zone of the previous and new snapshot |
| `distance_km` | `Δtrip_meter` when it agrees with the odometer (Δodometer − 1 ≤ Δtrip ≤ Δodometer + 1, so no reset and no lagging trip meter); otherwise `Δodometer` |
| `battery_*`, `charged_kwh` | Battery % at both ends, plus the kWh charged within the same window: the home charger's counter delta, plus the estimate of a detected public charge (unless it is flagged `possible_engine_charge`). The **add-on** turns this into energy: `(start − end) × kwh_per_pct + charged_kwh` (see [costs.md](costs.md#kwh-per-percent)). A negative result means the engine charged the battery on a PHEV. |
| `fuel_*` | Tank level at both ends. The add-on smooths these levels between refuels and takes the drop of the smoothed level as provisional litres, because fuel level sensors are noisy (see [costs.md](costs.md#fuel-gauge-noise)). |
| `kind` | `round_trip` when start and end are within 150 m or in the same zone, otherwise `one_way` |
| `flags` | `refuel_in_window`, `charge_in_window` |

If the same segment *also* shows the battery going up or the fuel going up, the trip is still created. The extra energy becomes a separate public-charge or refuel event, flagged for review (see below). One report can cover several drives; split such a trip on the Trips page.

### Snapshot boost

Optional, and off until an action is set. Cloud cars upload when they park, but Home Assistant only sees the upload at the car integration's next poll, which can be hours later. A late snapshot ends a trip late, and a trip window that runs into a home charge gets the wrong energy. When the car's integration has a "refresh now" action (Lynk & Co: `lynkco.force_update_data`), the Collector calls it on **local** hints, which arrive in real time:

| Hint | Refresh |
|---|---|
| The home charger linked to the car starts a session | at once: plugging in at home means a drive just ended |
| That session ends | after 2 min, for the final battery % |
| A chosen person leaves home | at once, so the previous drive is closed before the next starts |
| A chosen person arrives home | after 2 and after 10 min (the car may upload slowly) |

The car's own entities are not used as hints: they come from the same late cloud poll.

- Set it in the vehicle's **Change entities** (or when adding the vehicle) → *Snapshot boost*: the action (suggested from the odometer's integration when it has one with *force_update*, *refresh*, *update_data* or *poll* in its name; an action that does not exist is refused), the people, and `boost_max_per_day` (default 12, at most 48). Leave the action empty to switch it off.
- At most one refresh per minute (two phones arriving together give one), and at most `boost_max_per_day` per local day. Each call, and each skipped one with the reason, is in the diagnostics' decisions.
- `lynkco.force_update_data` only reads the Lynk cloud (two requests and an address lookup); it does not wake the car. Another integration's refresh action may wake the car: keep the daily limit low then.

## Home charge detection

Each charger subentry runs a small state machine:

```
IDLE ──(energy counter rises ≥ 0.05 kWh)──► CHARGING
CHARGING ──(power < stop_w for 10 min, or counter flat for 10 min)──► FINALISING
FINALISING ──(counter flat for 15 min since its last rise)──► IDLE   → emit charge.completed
FINALISING ──(counter rises again)──► CHARGING           (same session, e.g. a timer pause)
```

- **Energy comes only from the cumulative kWh counter**, never from integrating power. A sensor dropping to `unavailable` does nothing. The next valid counter value covers the gap. A counter that goes down (reset, replacement) gives a new base. Rises below 0.05 kWh while idle add up until they reach it. The session ends at the counter's last rise.
- **Pricing per increment.** Every time the counter rises by Δ kWh, `cost += Δ × price_now`, using the `price` entity's current state, or the fixed price when that is unavailable, or else the add-on's fallback electricity price. A night charge on a dynamic tariff is therefore priced correctly hour by hour. The session stores both `energy_kwh` and `cost`, plus the price samples with their source.
- **Vehicle attribution.** The session goes to the charger's assigned vehicle. Without one, the session is still recorded and lands in the review inbox.
- **Battery %.** `soc_start` is the battery % of the vehicle's last snapshot at or before the session's start. `soc_end` comes from the first snapshot after the end, up to 12 h later, because cloud cars report late. These values feed the [kWh-per-% learning](costs.md#kwh-per-percent).
- **Persistence.** The open session, its last counter value and its running cost are written to the Store on every change. Energy delivered while HA was down is in the counter and is counted at the next start. `charge.updated` events go out every 15 min.
- **Standby use.** A counter rise is judged by its average power over at least a minute. A rise slower than `stop_w` (default 100 W) is the charger's own standby use, for example the ~3 W a Shelly EV charger draws after the car is full: it is not added to a session and does not keep one open, and without a session it never adds up to a new one.
- Sessions below `min_session_kwh` (default 0.2) are discarded, since those are standby blips.

## External (public) charge detection

This applies to PHEV and BEV. Between two snapshots, an external charge is assumed when:

- `Δbattery_pct ≥ +3 %` (`external_charge_min_pct`), **and**
- the assigned home charger delivered `< 0.2 kWh` in that window.

The event carries `energy_kwh_estimated = Δbattery_pct × kwh_per_pct`, the place, the battery % at both ends and the time window. The add-on records it as a public charge priced at its *public charging price* setting, and puts it in the review inbox, where you enter the receipt's kWh and the price per kWh or the total amount.

The event also records whether the car itself reported charging (`charging_state`). When the segment includes driving and the car did not report charging (or `charging_state` is not mapped), the event is flagged `possible_engine_charge`: a PHEV can charge its battery from the engine. Its kWh are then not added to the trip, and the review item says so.

## Refuel detection

This applies to PHEV and ICE. Between two snapshots, a refuel is assumed when `Δfuel_l ≥ refuel_min_l` (default 3 L).

- `litres = Δfuel_l`, marked as an estimate, because the receipt is the truth.
- The suggested `price_per_l` comes from the `fuel_price` entity, else from the last refuel's price, else from the default fuel price in Settings. Status: `needs_review`.
- It counts as a full tank when the level afterwards is at least 92 % of the tank size.
- The place is the end point of the segment, the address being the fuel station's.
- The collector fires `autoledger_refuel_detected` so an automation can ask you for the receipt amount right away (example below).

## Idle consumption

When the battery or fuel drops between snapshots **without** a trip (pre-climate, standby, cabin heating while parked), an `idle` record is emitted, as long as the drop reaches the threshold (`idle_min_pct`, default 1 %, or `idle_min_l`, default 0.5 L) and the home charger delivered less than 0.2 kWh in that window. It is costed like a trip but reported separately as *"climate & standby"*, so the €/km of real driving is not distorted.

## Odometer readings

Every snapshot in which the odometer changed sends an `odometer.reading`. This gives the add-on a continuous odometer history, so km per month are known for a connected car before its first trip, and also for distance the trip detector would miss (for example while HA was down for days).

## Backfill

Service `autoledger.backfill` takes a `vehicle` and a `start` date. It reads the recorder history of the mapped entities (and the assigned chargers' counters) from that date **up to the moment live tracking began** and replays it through the detectors, one snapshot per burst of changes as in live tracking. Use it right after installing, to recover the last days (the HA recorder keeps about 10 days by default).

- Backfilled events get UUIDs derived from vehicle, type and time, so running backfill twice creates nothing twice.
- It stops where live tracking began, so nothing is detected twice. A start at or after that moment is refused. Gaps *after* that (HA down for days) are covered by the odometer readings; their km count, but no trips are made for them.
- Trips, idle records, refuels, public charges and odometer readings are backfilled. Home charge sessions are not: add those by hand on the Charging page if needed.
- The response tells how many snapshots and events it found.

## Delivery (outbox)

- Events are appended to the persisted outbox, then sent in batches of up to 100 to `POST /api/v1/ingest`.
- When delivery fails, retries back off: 10 s, 30 s, 2 min, 10 min, then every 10 min.
- The outbox is capped at 10 000 events. When the cap is reached, the oldest `charge.updated` progress event is dropped first, otherwise the oldest event.
- When delivery fails and the oldest waiting event is more than 24 h old, the Repair issue *AutoLedger add-on unreachable* is raised. It is removed after the next successful delivery.

## Exposed entities

One HA **device** per add-on vehicle that is not archived (manual vehicles such as the VW Up included), one per home charger, and one *AutoLedger* device for the review counter. Vehicle values come from the add-on summary, which is polled every 5 minutes and right after each delivery. Charger values are live from the collector. Money is in the add-on's currency (default EUR):

| Entity | Unit | Notes |
|---|---|---|
| `sensor.<car>_cost_this_month` | EUR | device_class `monetary`, state_class `total`, resets each month. Energy costs plus maintenance, expenses and depreciation. |
| `sensor.<car>_energy_cost_this_month` | EUR | Electricity and fuel only |
| `sensor.<car>_energy_cost_per_km` | EUR/km | Rolling 12 months, energy only (driving only once it is trip-based). No device class. |
| `sensor.<car>_total_cost_per_km` | EUR/km | Rolling 12 months, everything included |
| `sensor.<car>_distance_this_month` | km | device_class `distance` |
| `sensor.<car>_electricity_this_month` | kWh | device_class `energy`, state_class `total` |
| `sensor.<car>_fuel_this_month` | L | device_class `volume` |
| `sensor.<car>_fuel_consumption` | L/100 km | Rolling 12 months: from trips for a connected car, else full-to-full (see [costs.md](costs.md#consumption-figures)) |
| `sensor.<car>_electric_consumption` | kWh/100 km | Rolling 12 months, trips only. Attribute `electric_share` (PHEV). |
| `sensor.<car>_last_trip` | km | Attributes: `start_ts`, `end_ts`, `from`, `to`, `energy_kwh`, `fuel_l`, `cost` |
| `sensor.<car>_last_charge` | kWh | Attributes: `start_ts`, `end_ts`, `cost`, `avg_price`, `kind` |
| `sensor.<car>_odometer` | km | Latest known odometer, state_class `total_increasing` |
| `sensor.<car>_next_maintenance` | d | device_class `duration`. Days to the most urgent active schedule (negative when overdue). Attributes: `name`, `status`, `due_date`, `due_km`, `km_left`, `estimated_date`, `reason`, `schedules`, and the car's own `car_days_to_service` / `car_distance_to_service`. |
| `binary_sensor.<car>_maintenance_due` | — | device_class `problem`. On while a schedule is due soon or overdue. Attribute `items`. |
| `sensor.autoledger_items_to_review` | count | Number of items in the review inbox |
| `binary_sensor.<charger>_charging` | — | device_class `battery_charging`. A session is running (collector state, live) |
| `sensor.<charger>_session_energy` / `_session_cost` | kWh / EUR | Live values of the open session. Attribute `session_start`. |

## Services

The `vehicle` field is a device selector for AutoLedger devices; pick a vehicle, so there is no free-text ID. The `add_*` services forward to the add-on API, and they work for **manual** vehicles too: the add-on's manual vehicles are created as devices as well.

| Service | Fields |
|---|---|
| `autoledger.add_refuel` | `vehicle`, two of `litres`, `total` and `price_per_l`, `odometer`?, `full_tank` (default true), `station`?, `timestamp`? |
| `autoledger.add_charge` | `vehicle`, `energy_kwh`, `total` **or** `price_per_kwh`, `location`?, `timestamp`?. Adds a public charge. |
| `autoledger.add_odometer` | `vehicle`, `odometer`, `timestamp`? |
| `autoledger.backfill` | `vehicle`, `start` (date). Only for a vehicle with a Collector vehicle subentry. Returns `{from, until, snapshots, events}`. See [Backfill](#backfill). |
| `autoledger.resync` | No fields. Sends waiting events now and refreshes the summary. |

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

Under *Detection thresholds* and *Snapshot boost* in the vehicle's form:

| Option | Default | Meaning |
|---|---|---|
| `min_trip_km` | 0.5 | Smaller odometer deltas count as noise |
| `external_charge_min_pct` | 3 % | Threshold for detecting a public charge (PHEV/BEV) |
| `refuel_min_l` | 3 L | Threshold for detecting a refuel (PHEV/ICE) |
| `idle_min_pct` / `idle_min_l` | 1 % / 0.5 L | Thresholds for idle-consumption records |
| `boost_service`, `boost_persons`, `boost_max_per_day` | — / — / 12 | [Snapshot boost](#snapshot-boost) |

Charger subentry options, under *Session detection*: `stop_w` (default 100) and `min_session_kwh` (default 0.2). A session starts on the counter alone, never on power. `fixed_price` is used when no price entity is mapped or it is unavailable. When neither is available, the add-on's fallback electricity price is used. The price source is stored with every price sample.

## Diagnostics

The HA diagnostics download contains, with the token and location (latitude, longitude, address) redacted: the entity mapping of every subentry; per vehicle the detector state (last committed snapshot, recent battery readings, pending battery look-ups after a charge, the boost counter); per charger the session machine with any open session; the outbox's length, oldest entry, last delivery and last error; the fallback electricity price; and the last 50 detector decisions with their reasons (`Lynk & Co: trip.recorded (trip 6.3 km (trip_meter), battery -11.5 %, fuel -0.4 L)`).
