# AutoLedger add-on & GUI

The add-on holds every record, calculates every cost and offers the web GUI. It is opened from the HA sidebar through Ingress and also works in the HA Companion app on a phone.

## Installation

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories**, then add `https://github.com/kramat/autoledger`.
2. Install **AutoLedger**, enable **Show in sidebar**, and start it.
3. Open it. With no vehicles yet, the overview asks you to add your first vehicle. Check the default prices and the currency under **Settings**.
4. For automatic tracking, install the [Collector](collector.md#setup): in HACS, **⋮ → Custom repositories**, add `https://github.com/kramat/autoledger` with category **Integration**, install **AutoLedger Collector** and restart HA. It discovers the add-on by itself.

## Add-on options (Supervisor configuration tab)

Only things needed before the GUI can start live here. Everything else is set in the GUI.

| Option | Default | Meaning |
|---|---|---|
| `log_level` | `info` | `debug`, `info`, `warning` or `error` |
| Network → port `8099/tcp` | empty (internal only) | Set a host port to reach the API from your own scripts outside HA. Requests need the token. |

## GUI overview

```
┌ AutoLedger ─────────────────────────────────────────────────────── [Lynk & Co 01 ▾] [This month ▾] ┐
│ Overview │ Trips │ Fuel │ Charging │ Maintenance │ Costs │ Reports │ Review ③ │ Vehicles │ Settings │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- The **vehicle selector** offers one vehicle or *All vehicles*.
- The **period selector** offers this month, last month, this year, last year, last 12 months, all time or a custom range. It applies to the overview and the trips page. Reports has its own period. The other list pages always show the full history (newest first), so back-dated entries are easy to find.
- Both stay selected while you move between pages and are kept in the URL, so deep links work.
- Every list can be exported as CSV for the selected vehicle.
- A deleted record can be restored with **Undo** for a few seconds. Deletes are soft, so the API can restore it later too.
- The interface is in English or Dutch (see [Settings](#settings)). Numbers and dates follow the language.

### Overview

Per vehicle, one card with:

- distance this period and the odometer;
- total cost and cost per km;
- fuel cost, litres and L/100 km; electricity cost, kWh and kWh/100 km (or kWh and the number of charges for a car without trips);
- maintenance, other costs and, when switched on, depreciation;
- the last 12 months: km, cost per km (total and energy), L/100 km and, for a PHEV, the electric share of km;
- the last trip (from → to, km, cost);
- climate & standby energy and cost, when there was any;
- a running charge session (kWh and cost so far), or else the last charge;
- the last refuel;
- the next maintenance due (by date or km, whichever comes first).

With *All vehicles* and more than one vehicle, a combined card follows.

Below the cards, for the last 12 months, as a chart or a table:

- **cost per month**, stacked: fuel, electricity, maintenance, other (with depreciation);
- **distance per month**.

When items wait in the review inbox, a notice with the count links to it.

### Trips

Trips of connected cars are recorded by the Collector. Trips can also be added by hand. A manual vehicle's distance comes from its odometer readings and refuels.

- **List** columns: date, start → end time (`~` when the start is estimated), from → to (address or zone name), km, kWh, L (✓ when corrected at a full tank), cost and cost per km. Round trips show *"⟲ Home"*. Totals for the period are shown above the list.
- **Map** toggle: start and end markers of the listed trips, drawn on OpenStreetMap. A trip's line is drawn straight, because no route is recorded.
- **Details** of a trip:
  - odometer, battery % used, energy charged in between, tank levels and the distance source;
  - how the cost was calculated, with every input listed;
  - the note.
- **Actions**:
  - **Edit** start and end time, places, kind (one way / round trip), km, battery %, kWh, litres and the note.
  - **Merge** with the previous or next trip.
  - **Split** a trip: enter the km and time of the stop, and optionally the stop's place. Energy is divided by distance.
  - **Delete** a trip. It is soft-deleted and can be restored.
  - **Add trip**.
- **Climate & standby**: energy used while parked (pre-heating, standby), with its cost. It counts in the energy cost but not in the consumption per km. Records can be edited and deleted.

### Charging

- **List** of all sessions: start, place (home charger, or provider and address), kWh, battery % from → to, average price per kWh, cost and status (*charging now*, *needs price*, *kWh estimated*). Totals are shown below.
- **Home sessions** are priced per kWh at the moment it was delivered, using the electricity price sensor. A running session is shown live.
- **Edit** a session to change its price, in one of these ways:
  - a price per kWh, optionally with a start fee;
  - the total amount;
  - **free** (for example charging at work);
  - the live electricity price (home sessions).

  Editing re-prices this session and, through the [battery cost basis](costs.md#battery-and-tank-cost-basis), all trips after it.
- **Add public charge**: vehicle, type, kWh, start and end, price, battery % at start and end, provider, location and a note.
- **Efficiency card** per car with a battery: the *kWh from the wall per battery %* in use and where it comes from (set by you, learned, or from the capacity), the learned value and how many sessions it is based on. You can set your own value, and switch back to the learned one.

### Fuel

Two lists: **Refuels** and **Odometer readings**.

- **Refuels** columns: date, odometer, litres, price per litre, total, tank (full or partial), L/100 km, station and receipts. L/100 km is shown on the refuel that closes a full-to-full interval.
- **Add refuel**: date and time, odometer, full tank (default yes), two of litres, total and price per litre (the third is calculated), station, note, and receipt photos or PDFs.
- **Auto-detected refuels** arrive with an estimated litre count and a suggested price per litre, and appear in the review inbox until you confirm them. Confirming usually means typing the receipt total.
- **Odometer readings**: date, odometer and note. Refuels and maintenance entries with an odometer value count as readings too.

### Maintenance

- **Schedules** (reminders), for example *Service every 12 months or 15 000 km* or *APK yearly*:
  - Each schedule has a name, a category, an interval in months and/or km, a *last done* date and odometer, and how many days or km in advance it reminds you (default 30 days or 1000 km). A schedule can be paused.
  - Maintenance entries of the schedule's category, or linked to the schedule, move *last done* forward by themselves.
  - **Next due** is calculated from the date interval, the km interval and the current odometer. For a km interval, the date is estimated from the average km per day over the last 90 days. The status is *on track*, *due soon*, *overdue* or *not known yet*.
  - **Log as done** opens a new maintenance entry for the schedule.
  - The most urgent schedule is shown on the overview and as an HA sensor, `sensor.<car>_next_maintenance`.
- For cars that report it (Lynk: `days_to_service` and `distance_to_service`), the car's own service countdown is shown next to the schedules as a cross-check.
- **Log**: date, category, description, schedule, garage, invoice (photo or PDF), odometer and cost. Categories: service, inspection (APK), tyres, repair, battery, cleaning, other. An entry counts for every schedule of its category, or only for the schedule you pick.

### Costs

Other costs, one list:

- date, category, amount, repeats, note and receipts;
- categories: insurance, road tax (*MRB*), parking, tolls, car wash, fine, accessories, lease, subscription, other;
- **repeats**: one-off, monthly, quarterly or yearly. A recurring cost has the amount per period, a start date and an optional end date. It is spread over the months it covers: a yearly insurance of 600 counts as 50 per month.
- **for**: one vehicle, or shared by several (with two or more vehicles): split equally, by km driven, or with fixed percentages. The amount is the whole bill; each vehicle counts its part of every month (see [costs.md](costs.md#shared-costs)). With one vehicle selected at the top, the list also shows the shared costs it takes part in, with the vehicles in the *Vehicle* column.

Depreciation is set per vehicle (see [Vehicles](#vehicles)).

### Reports

The page has its own period: a calendar year (the current one up to today) or a custom range, grouped per month, quarter or year. It covers the selected vehicle, or all vehicles side by side with a combined column.

- **Period table**, per vehicle:
  - distance;
  - total cost, total per km and energy per km;
  - cost per category: fuel, electricity, maintenance, other, depreciation;
  - L/100 km, kWh/100 km and the electric share;
  - climate & standby;
  - number of trips, refuels, charges and maintenance entries;
  - per year: km, total cost and maintenance, scaled to 365 days so vehicles with a shorter history compare fairly.
- **Cost per month, quarter or year**: stacked chart or table.
- **Trends**: monthly lines for total cost per km, L/100 km and kWh/100 km since the first data, and consumption per season (winter, spring, summer, autumn).
- **Export** the report as XLSX or CSV. Raw records and the JSON backup are under [Settings](#settings).

### Review inbox

This lists everything the system was not sure about. Each item has quick actions.

| Reason | Quick actions |
|---|---|
| Refuel detected | Correct the litres and enter the total, keep the suggestion, or *not a refuel* (deletes it) |
| Charge away from home | Correct the kWh and enter the price per kWh or the total, mark it free, or *not a charge* |
| Battery went up while driving | The same as a charge away from home, or *charged by the engine* (deletes it, no cost) |
| Home charge without a vehicle | Pick a vehicle, or remove the session |
| Collector data that could not be processed | Dismiss |

The inbox count is also `sensor.autoledger_items_to_review`, so you can show it on your car dashboard.

### Vehicles

- **Fields**:
  - name, make, model, year, licence plate;
  - type (`ICE`, `PHEV`, `BEV`), fuel (petrol, diesel, LPG);
  - tank size (L), usable battery (kWh), and the wall kWh per battery % (empty: from the capacity);
  - chart colour and a note.
- **Starting point**: the date tracking starts and the odometer on that date. Reports start there.
- **Ownership**, optional: purchase date and price, expected resale date and value. With *Count depreciation in the costs* switched on, the loss of value is spread evenly per month and counted in the totals (see [costs.md](costs.md#recurring-expenses-and-depreciation)).
- **Archive** a sold vehicle: it is hidden from the vehicle selector and kept in reports. **Unarchive** brings it back.

### Settings

- **General**: language (automatic from the browser, English or Dutch).
- **Prices and currency**:
  - currency (ISO code);
  - fallback electricity price per kWh;
  - default public charging price per kWh;
  - default fuel price per litre for petrol, diesel and LPG.
- **Export**: all records in one XLSX workbook (a sheet per type), or one CSV file per type.
- **Import**: refuels, maintenance, odometer readings or other costs from a CSV file, with column mapping (guessed from English and Dutch headers), decimal separator and date order. A preview shows each row as ok, already there or with an error; nothing is saved until you click **Import**.
- **Backup**: a JSON backup of everything, optionally with the receipt photos and invoices. **Restore** it into an empty add-on, or add what is missing and keep what is there. The current database is copied to `/data/backups` first.
- **API token**: show, copy, or create a new one.
- **Collector**: when the Collector last sent data.

## Manual-only vehicle (the VW Up workflow)

1. **Vehicles → Add vehicle**: VW Up, 2018, `ICE`, petrol, tank 35 L, tracking start date and odometer.
2. At every fuel stop: **Fuel → Add refuel** with litres, total and odometer. Leave *full tank* ticked if you filled up. The add-on calculates L/100 km full-to-full, km driven and cost per km.
3. Optionally, now and then: an **odometer reading** (**Fuel → Odometer readings → Add reading**, or the `autoledger.add_odometer` service). This keeps monthly km accurate between refuels.
4. **Maintenance** and **Costs** work exactly as for a connected car.

There are no recorded trips for a manual vehicle. Distance per month is spread between readings (see [costs.md](costs.md#distance-for-manual-vehicles)).

## Technology

| Layer | Choice | Why |
|---|---|---|
| Base image | `ghcr.io/home-assistant/{arch}-base-python` | Official add-on base image, built for amd64 and aarch64 |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic | Same language as HA, with typed models and an OpenAPI spec for free |
| Database | SQLite in `/data` (WAL mode) | One file, included in HA backups, plenty for one household |
| Frontend | Vue 3 + Vite + TypeScript, ECharts, Leaflet | Small bundle that works under the Ingress sub-path (all URLs relative) |
| Language | English and Dutch | A small built-in `t()` (`src/i18n/`): per-area text files, with the Dutch type-checked against the English so a missing text fails the build. Numbers and dates follow the chosen language. |
| Theming | Light and dark, following the device's colour scheme | No setting needed |
