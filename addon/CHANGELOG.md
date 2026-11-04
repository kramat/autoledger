# Changelog

## Collector 1.0.1

- A home charge session now ends when the car is full even if the charger keeps drawing a few watts on standby.
  Before, every tiny rise of the kWh counter kept the session open, so it never ended. A counter rise slower than
  *Not charging below* (default 100 W) now counts as standby: it is not part of a session and cannot start one.
  A session that is open when you update ends by itself within about 15 minutes.

## 1.0.0

The first complete release: everything in the [history](https://github.com/kramat/autoledger/blob/main/docs/history.md)
is in, and the documentation describes AutoLedger as it is.

- Vehicles the Collector sends data for are now marked as Collector vehicles. Until now every vehicle stayed
  *manual*, so for a connected car *Log as done* did not fill in the odometer and the Trips page showed the text for
  manual cars. The database upgrade fixes existing vehicles.
- Collector 1.0.0: the charger option *Charging above* (it had no effect: a session starts on the kWh counter) and
  the vehicle role *Charging cable connected* (nothing used it) are gone. Saved settings keep working.

## 0.6.0

- Nederlands: the whole interface is now available in Dutch. **Settings → General → Language** chooses English,
  Nederlands, or *Automatic* (the default), which follows each device's browser language. Dates, numbers and money
  follow the language as well.
- Error messages from the add-on come in the interface language too.
- The add-on's options in Home Assistant have a Dutch description.
- Collector 0.6.0: Dutch translation of the setup screens, entities, services and repair notices. Home Assistant
  uses it when your profile language is Nederlands.

## 0.5.1

- Foldables and phones: on narrow screens (a folded Galaxy Z Fold, most phones) every record table shows its rows as
  cards with labelled values, so Edit and Delete are always in reach without scrolling sideways. Unfolded, tables stay
  tables and the Edit/Delete column stays at the right edge when a table is wider than the screen.
- The report and overview tables keep their first column in view while the figures scroll.
- A more compact header on narrow screens: name and filters on one line.

## 0.5.0

- Receipt photos and invoices: attach a photo or PDF to a refuel, a maintenance entry or a cost, from your phone's
  camera or files. Large photos are made smaller before upload. Tables show a 📎 for records with a receipt.
- Depreciation: with a purchase price and date, and an expected resale value and date, a vehicle can count its loss of
  value in the costs, the same amount every month from the tracking start on. Off by default, per vehicle.
- Backups can include the receipt files (Settings → Backup → *Include receipt photos and invoices*).
- Fix: on phones, pages with a table could scroll a little sideways.
- Collector 0.5.0: *snapshot boost* asks the car's integration for fresh data when the home charger starts or stops
  and when someone leaves or comes home, and a fuel price entity can suggest the price of detected refuels.

## 0.4.0

- Maintenance schedules: *every 12 months or 15 000 km*, *APK yearly*. Logged maintenance moves a schedule
  forward by itself (linked, or by category), and the next due date is estimated from how much you drive.
  Due soon and overdue show on the Maintenance page, the overview and in Home Assistant (Collector 0.4.0).
  The car's own service countdown is shown next to them when the Collector maps it.
- Reports: a year (or any period) per month, quarter or year, cars side by side with figures per year,
  trends of €/km and consumption per month, and consumption per season. Export as XLSX or CSV.
- Export of all records as one Excel workbook, or per type as XLSX.
- Full JSON backup and restore (into an empty add-on, or adding only what is missing).
- CSV import of refuels, maintenance, odometer readings and other costs, with a preview, column mapping,
  decimal commas and day-first dates. Rows that are already there are skipped.

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
