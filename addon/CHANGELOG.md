# Changelog

## 0.3.1

- Fuel gauge noise is smoothed: between refuels the tank level can only go down, so a dip that comes
  back on the next report is handed back instead of being charged. Noise no longer adds up between refuels.
- The correction at a full tank goes to the trips that used fuel, so PHEV trips on electricity stay at 0 L.
- Trip details show the gauge litres next to the costed litres.

## 0.3.0

- Trips: every drive of a car in the AutoLedger Collector with km, kWh, litres and cost, on a list or a map.
  Details show how the cost was calculated; split a trip with a stop, merge two, or add one by hand.
- Energy is now counted when it is used: charges and refuels fill the battery and the tank, trips use them
  at their average price. Before a car's first trip, purchases count as before.
- Fuel per trip is corrected at every full tank. kWh per battery % is learned from home charges
  (Charging → Efficiency), or set by you.
- Climate & standby: energy used while parked, in the energy cost but not in € per km.
- Overview: last trip, kWh/100 km and the electric share of km.

## 0.2.0

- Charging: home sessions from the AutoLedger Collector (priced per kWh with your electricity price),
  public and manual charges with price per kWh, total or free. Electricity is now part of all totals.
- Review inbox for detected refuels, public charges and sessions without a vehicle.
- Collector API: `POST /api/v1/ingest`, idempotent and fault tolerant.
- The add-on announces itself to Home Assistant, so the Collector can set itself up.
- Vehicles: wall kWh per battery % (for example 0.165 for the Lynk & Co 01).

## 0.1.0

- First release (milestone M1): vehicles, refuels, odometer readings, maintenance log,
  one-off and recurring expenses, overview with monthly costs and km, CSV export.
