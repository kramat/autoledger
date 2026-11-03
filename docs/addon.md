# AutoLedger add-on & GUI

The add-on holds every record, calculates every cost and offers the web GUI. It is opened from the HA sidebar through Ingress and also works in the HA Companion app on a phone.

## Installation

1. **Settings → Add-ons → Add-on store → ⋮ → Repositories**, then add `https://github.com/kramat/autoledger`.
2. Install **AutoLedger**, enable **Show in sidebar**, and start it.
3. Open it. With no vehicles yet, the overview asks you to add your first vehicle. Check the default prices and the currency under **Settings**.
4. For automatic tracking, install the [Collector](collector.md#setup) (from M2). It discovers the add-on by itself.

## Status per milestone

| Page | Available |
|---|---|
| Overview, Fuel (refuels + odometer readings), Maintenance (log), Costs, Vehicles, Settings, CSV export | **M1** (built) |
| Charging, Review inbox | **M2** (built) |
| Trips (list, map, details, split, merge), climate & standby, efficiency card | **M3** (built) |
| Maintenance schedules and reminders, Reports, XLSX, JSON backup, CSV import | M4 |
| Attachments, depreciation | M5 |

The sections below describe the full design. Pages and features that are not built yet are hidden in the GUI.

## Add-on options (Supervisor configuration tab)

Only things needed before the GUI can start live here. Everything else is set in the GUI.

| Option | Default | Meaning |
|---|---|---|
| `log_level` | `info` | `debug`, `info`, `warning` or `error` |
| Network → port `8099/tcp` | empty (internal only) | Set a host port to reach the API from your own scripts outside HA. Requests need the token. |

## GUI overview

```
┌ AutoLedger ────────────────────────────────────────────── [Lynk & Co 01 ▾] [This month ▾] ┐
│ Overview │ Trips │ Charging │ Fuel │ Maintenance │ Costs │ Reports │ Review ③ │ ⚙          │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

- The **vehicle selector** offers one vehicle or *All vehicles*.
- The **period selector** offers this month, last month, this year, last year, last 12 months, all time or a custom range. It applies to the overview. List pages always show the full history (newest first), so back-dated entries are easy to find.
- Both stay selected while you move between pages and are kept in the URL, so deep links work.
- Every list can be exported as CSV for the selected vehicle.
- A deleted record can be restored with **Undo** for a few seconds. Deletes are soft, so the API can restore it later too.
- Every automatically created record shows a badge: **auto**, **auto · edited**, **manual** or **estimated**.

### Overview

Per vehicle, one card with:

- km this period, energy cost, total cost, €/km (energy and total);
- electricity and fuel consumption, and for a PHEV the electric share of km;
- the last trip (from → to, km, €);
- the next maintenance due (by date or km, whichever comes first);
- a live charge session, if one is running (kWh, €, power).

Below the cards:

- a **cost per month** stacked bar chart: electricity, fuel, maintenance, other;
- a **km per month** chart;
- the **review inbox** count with a link.

### Trips

*Connected vehicles only. A manual vehicle shows its distance between odometer readings instead.*

- **List** columns: date, start → end time, from → to (address or zone name), km, kWh, L, cost and consumption. Round trips show *"⟲ Home"*.
- **Map** toggle: start and end markers of the filtered trips, drawn on OpenStreetMap. A trip's line is drawn straight, because no route is recorded.
- **Detail panel**:
  - edit start and end time, places, km, kWh and litres (edited fields get a lock icon);
  - add a note;
  - see how the cost was calculated, with every formula input listed.
- **Actions**:
  - **Merge** two adjacent trips.
  - **Split** a trip: enter the km and time of the stop, and energy is divided by distance.
  - **Delete** a trip. It is soft-deleted and can be restored.
  - **Add trip manually**.

### Charging

- **List** of all sessions:
  - date, place (*home* / address);
  - kWh, battery % from → to, duration;
  - average €/kWh, cost, source (*home charger*, *public*, *manual*).
- **Home sessions** are priced per kWh at the moment it was delivered. A running session is shown live. *(A price curve per session follows later.)*
- **Edit price**, three ways:
  - set €/kWh;
  - set the total amount;
  - mark it **free** (for example charging at work).

  Editing re-prices this session and, through the [battery cost basis](costs.md#battery-and-tank-cost-basis), all trips after it.
- **Add public charge**: date, place, kWh (or battery % from → to, converted to kWh), price or total, and optionally a session fee and a provider.
- **Efficiency card** per car with a battery: the *kWh from the wall per battery %* in use and where it comes from (set by you, learned, or from the capacity), the learned value and how many sessions it is based on. You can set your own value, and switch back to the learned one.

### Fuel

- **List** of refuels:
  - date, odometer, litres, €/L, total, station;
  - full tank ✓;
  - consumption since the previous full tank (L/100 km).
- **Add refuel**. The form needs litres plus **either** €/L **or** the total; the third value is calculated. It also takes odometer, full tank (default yes), station and optionally a receipt photo.
- **Auto-detected refuels** arrive with an estimated litre count and a suggested €/L, highlighted until you confirm them. Confirming usually means typing the receipt total.
- The **consumption chart** shows L/100 km per full-to-full interval.

### Maintenance

- **Log**: date, odometer, category, description, garage, cost, attachments (invoice PDF or photo). Categories:
  - service, APK/MOT, tyres, repair, battery, cleaning;
  - cosmetic, other, or custom.
- **Schedules** (reminders), for example *Service every 12 months or 15 000 km* or *APK yearly*:
  - Each schedule has a *last done* date and odometer. It is updated automatically when you log a matching maintenance entry.
  - **Next due** is calculated from the date interval, the km interval and the current odometer, plus the average km per day for an estimated due date.
  - Shown on the overview and as an HA sensor, `sensor.<car>_next_maintenance`.
- For cars that report it (Lynk: `days_to_service` and `distance_to_service`), the car's own service countdown is shown next to the schedule as a cross-check.

### Costs

Non-energy costs.

- **One-off expenses**:
  - date, category, amount, note, attachment;
  - categories: parking, tolls, car wash, fine, accessories, other.
- **Recurring expenses**:
  - category, amount, interval (monthly, quarterly, yearly), start and end date;
  - categories: insurance, road tax (*MRB*), lease, subscription (charge card, app), loan;
  - reports spread them over the months they cover.
- **Ownership**, optional per vehicle:
  - purchase price and date, expected resale value and date;
  - gives a straight-line depreciation per month, which you can include in or exclude from the totals.

### Reports

- **Period report** for one vehicle or all vehicles:
  - km;
  - kWh and L;
  - cost per category;
  - €/km (energy only and total);
  - kWh/100 km and L/100 km;
  - number of trips, charges and refuels.
- **Compare** vehicles side by side (for example Lynk vs VW Up: €/km, L/100 km, maintenance per year).
- **Trends**: monthly lines for €/km and consumption, plus a seasonal view (winter vs summer consumption).
- **Export**: CSV or XLSX of the report or of the raw records, and a full JSON backup (see [Settings](#settings)).

### Review inbox

This lists everything the system was not sure about. Each item has quick actions.

| Reason | Quick actions |
|---|---|
| Refuel without a confirmed price | Enter total or €/L, or confirm the suggestion |
| Public charge without a price | Enter total or €/kWh, or mark free |
| Charge session without a vehicle | Pick a vehicle |
| Segment with driving and a battery increase | *Public charge* / *Engine charged* (no cost) |
| Odometer gap (km missing between trips, e.g. HA was down) | Create a trip for the gap, or ignore |
| Unusual values (consumption more than 3× the average) | Confirm or edit |

The inbox count is also `sensor.autoledger_review_items`, so you can show it on your car dashboard.

### Vehicles (⚙ → Vehicles)

- **Fields**:
  - name, plate, make, model, year;
  - type (`ICE`, `PHEV`, `BEV`), fuel type (petrol, diesel, LPG);
  - tank size (L) and usable battery capacity (kWh);
  - color and icon for charts.
- **Tracking source**:
  - *Home Assistant collector*, which shows the link status and the last snapshot time;
  - or *manual*.
- **Starting point**: an initial odometer reading and date. Reports start there.
- **Archive** a sold vehicle: it is hidden from selectors and kept in reports.

### Settings

- **Prices**:
  - fallback electricity price (€/kWh);
  - default public charging price (€/kWh);
  - default fuel price per fuel type.
- **General**: currency, language, first day of the week, number and date format.
- **Collector**: API token (show and regenerate), connected collectors, last delivery.
- **Data**:
  - JSON backup download and restore;
  - CSV import for refuels, maintenance and odometer readings (for history from a spreadsheet or another app), with column mapping;
  - recalculate all costs.

## Manual-only vehicle (the VW Up workflow)

1. **⚙ → Vehicles → Add**: VW Up, 2018, `ICE`, petrol, tank 35 L, starting odometer.
2. At every fuel stop: **Fuel → Add refuel** with litres, total and odometer. Leave *full tank* ticked if you filled up. The add-on calculates L/100 km full-to-full, km driven and €/km.
3. Optionally, now and then: an **odometer reading** (**Fuel → ⋮ → Add odometer reading**, or the `autoledger.add_odometer` service). This keeps monthly km accurate between refuels.
4. **Maintenance** and **Costs** work exactly as for a connected car.

There are no trips for a manual vehicle. Distance per month is spread between readings (see [costs.md](costs.md#distance-for-manual-vehicles)).

## Technology

| Layer | Choice | Why |
|---|---|---|
| Base image | `ghcr.io/home-assistant/{arch}-base-python` | Official add-on base image, built for amd64 and aarch64 |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic | Same language as HA, with typed models and an OpenAPI spec for free |
| Database | SQLite in `/data` (WAL mode) | One file, included in HA backups, plenty for one household |
| Frontend | Vue 3 + Vite + TypeScript, ECharts, Leaflet | Small bundle that works under the Ingress sub-path (all URLs relative) |
| Language | English | Dutch to be added later with `vue-i18n`. Numbers and dates already follow the browser locale. |
| Theming | Reads the HA theme's CSS variables when available, light and dark | Looks native in the sidebar |
