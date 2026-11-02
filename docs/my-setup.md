# Reference setup

This is the setup AutoLedger is designed and tested against first: a Home Assistant OS 18.4 / Core 2026.10 installation in Leidschendam (NL), time zone Europe/Amsterdam.

| Vehicle | Type | Tracking |
|---|---|---|
| Lynk & Co 01 | PHEV, petrol | Collector (Lynk & Co integration + Shelly EV charger) |
| VW Up (2018) | ICE, petrol | Manual |

## Lynk & Co 01: entity mapping

Prefix: `sensor.lynk_co_l6tcx2e73ne015159_lynk_co_`

| Role | Entity | Example value |
|---|---|---|
| `odometer` | `…_odometer` | 63445 km (1 km resolution) |
| `trip_meter` | `…_trip_meter2` | 1382.0 km (0.1 km resolution). Preferred for distance. |
| `battery_level` | `…_battery` | 66.5 % |
| `fuel_level` | `…_fuel_level` (**litres**) | 16.0 L |
| `location` | `…_latitude` + `…_longitude` (or `device_tracker.lynk_co_l6tcx2e73ne015159_lynk_co_vehicle_tracker`) | 52.0893, 4.4003 |
| `address` | `…_address` | "Duinmeierij 118, Leidschendam-Voorburg" |
| `charging_state` | `…_charge_state` | Idle |
| `plug_state` | `…_charger_connection_status` | Disconnected |
| `fuel_flap` | `…_tank_flap_status` | TANK_FLAP_CLOSED |
| `running` | `binary_sensor.lynk_co_l6tcx2e73ne015159_lynk_co_vehicle_is_running` | off. Never seen as `on`, so live mode is **not** used. |
| `car_timestamp` | `…_last_updated_by_car` | 2026-11-02T12:42:56.941Z |
| Service countdown (shown in Maintenance) | `…_days_to_service`, `…_distance_to_service` | 654 days, 28 163 km |
| Boost service (optional) | `lynkco.force_update_data` | — |

Vehicle parameters:

- Battery: **14.1 kWh usable** (17.6 kWh gross).
- Wall energy for a full charge: an empty-to-full charge on the Shelly typically takes **≈ 16.5 kWh**. The starting `kwh_per_pct` is therefore **0.165** wall-kWh per %, which means about 85 % charging efficiency. Learning from home sessions refines it after that.
- Tank: about 51 L (to confirm).
- Public charging happens 1–2 times per month. Those sessions go through the review inbox with the default public price.

### How this car's data actually behaves

This was observed in the HA history from 30 Oct to 2 Nov 2026, and it shaped the design:

- **Data arrives as sparse snapshots.** `last_updated_by_car` changed only three times in three days. The car uploads when it parks or wakes, and HA picks the upload up at its next poll, at :58 past the hour. On 2 Nov the car reported at 13:42 and HA had the values at 13:58.
- **A whole drive shows up as one jump.** It went from 63 439 to 63 445 km, battery 78.0 to 66.5 % and fuel 16.4 to 16.0 L in a single update.
- **The tracker never left `home`** during that drive, and `vehicle_is_running` never turned `on`. A round trip therefore looks like *home → home, 6.3 km*.

→ **Snapshot mode** is the right trip mode. Trips are reported per segment, as round trip or one way, with an estimated start time. Optionally, *snapshot boost* can call `lynkco.force_update_data` after the lock changes, to split drives with stops into separate trips. That needs testing for its effect on the 12 V battery and the cloud rate limits.

### Collector setup for the Lynk

**Settings → Devices & services → AutoLedger → Add vehicle**:
1. Pick *Lynk & Co 01* and the odometer `sensor.lynk_co_l6tcx2e73ne015159_lynk_co_odometer`.
2. The next step pre-fills the other entities from the same device: trip meter 2, battery, fuel level (litres), latitude/longitude or the device tracker, address, charge state, charger connection status and `last_updated_by_car`.

Set **Wall kWh per battery %** to `0.165` on the add-on's Vehicles page.

## Shelly EV charger: charger subentry

| Role | Entity | Notes |
|---|---|---|
| `energy` | `sensor.shelly_ev_charger_energy` | kWh, `total_increasing`, ≈ 1003 kWh |
| `power` | `sensor.shelly_ev_charger_power` | W. **Drops to `unavailable` every 5–30 min**, so it is only used as a start/stop hint and never for energy. |
| `switch` | `switch.shelly_ev_charger` | |
| `price` | `sensor.cic_electricity_price_used` | €/kWh from Quatt, currently 0.19 |
| `vehicle` | Lynk & Co 01 | Fixed assignment (only one plug-in car) |

## VW Up (2018): manual vehicle

- Type `ICE`, petrol. Tank about 35 L (1.0 MPI; to confirm).
- At each fuel stop, log litres, total and odometer, from the GUI on your phone or with an HA dashboard button that calls `autoledger.add_refuel`.
- Maintenance:
  - APK schedule, yearly;
  - service schedule, every 12 months or 15 000 km (adjust to the VW service plan).
- It is compared side by side with the Lynk in **Reports → Compare**.

## Car dashboard integration

The existing HA dashboard `car-dashboard` ("Auto") gets an extra **Kosten** section with:

- `sensor.lynk_co_01_cost_this_month`, `…_cost_per_km` and `…_last_trip`;
- the live session of the Shelly charger, from `sensor.shelly_ev_charger_session_cost`;
- the review count;
- a shortcut card to the AutoLedger panel.

The entity names here are examples; the final ones are decided in M2.
