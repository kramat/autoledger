# Changelog

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
