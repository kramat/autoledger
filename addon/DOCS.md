# AutoLedger

## Getting started

1. Start the add-on and open **AutoLedger** from the sidebar.
2. Go to **Vehicles → Add vehicle**. For *Tracking starts on*, use the earliest date you have data for, together with the odometer value on that date.
3. Check the currency and default prices under **Settings**.
4. Add refuels under **Fuel**. Enter two of litres, total and price per litre; the third is calculated. Tick *Filled the tank completely* when you filled up: L/100 km is calculated from one full tank to the next.
5. Add maintenance under **Maintenance**, and insurance, road tax, parking and so on under **Costs**. A recurring cost (for example a yearly insurance) is spread over the months it covers.

Older data can be entered with its original date. All lists show the full history.

## How km are counted

Distance comes from odometer values: the vehicle's starting value, odometer readings, and the odometer of refuels and maintenance. Between two values the km are spread evenly over time. After the last known value there is no estimate, and the overview tells you how far the data goes.

For a car in the AutoLedger Collector, every drive also becomes a **trip** with km, kWh, litres and cost (Trips page). Right after installing the Collector, run the `autoledger.backfill` action (Developer tools → Actions) with a start date to recover the last days from Home Assistant's history.

## Options

| Option | Meaning |
|---|---|
| Log level | How much the add-on writes to its log |
| Network: port 8099 | Leave empty to keep the API internal. Set a port to use the API from your own scripts; send the token from **Settings** as `Authorization: Bearer <token>`. |

## Maintenance reminders

Under **Maintenance → Schedules**, add what recurs: *Service every 12 months or 15 000 km*, *APK every year*. Enter when it was last done; after that, every maintenance entry of the same category (or linked to the schedule) moves it forward by itself. **Log as done** fills in the entry for you. A schedule is *due soon* within its reminder window (default 30 days or 1 000 km) and *overdue* after the date or km. Km-based dates are estimated from how much the car drove in the last 90 days.

With the AutoLedger Collector 0.4.0, each car gets `sensor.<car>_next_maintenance` (days to the next due item), `binary_sensor.<car>_maintenance_due`, and the event `autoledger_maintenance_due` for your own notifications.

## Reports

**Reports** shows a calendar year (or any period) per month, quarter or year, with the cars side by side. *Per year* figures scale the period to 365 days, so a car with a shorter history compares fairly. Below that are monthly trends of € per km and consumption, and consumption per season. **Export XLSX / CSV** downloads the report.

## Language

AutoLedger speaks English and Dutch. Under **Settings → General → Language**, *Automatic* (the default) follows the language of each phone or browser; *English* and *Nederlands* fix it for everyone. The AutoLedger Collector follows your Home Assistant profile language.

## Receipts and depreciation

**Receipts.** In the dialog of a refuel, a maintenance entry or a cost, **Add photo or PDF** attaches a receipt or invoice. On a phone this offers the camera. Photos over 1.5 MB are made smaller (2000 px JPEG) before they are uploaded; PDFs and HEIC photos are kept as they are, up to 20 MB. A 📎 in the table marks records with a receipt.

**Depreciation.** On **Vehicles**, fill in the purchase price and date, the expected resale value and date, and tick *Count depreciation in the costs*. The loss of value (purchase − resale) is spread evenly over the months in between and counted from the vehicle's tracking start up to today, as a separate *Depreciation* line in the overview and the reports. It is included in the total cost and €/km, so switch it off when you only want running costs.

## Data and backups

Everything is stored in the add-on's data folder and included in Home Assistant backups. Before each database upgrade, the add-on also makes a copy in `backups/` inside that folder.

Under **Settings**:

- **Export**: all records as one Excel workbook, or one CSV per type.
- **Import CSV**: refuels, maintenance, odometer readings or other costs from a spreadsheet. The preview shows how each row is read (columns, decimal comma, day-first dates) before anything is saved, and rows that are already there are skipped.
- **Backup**: a JSON file with everything, to move to another installation. Tick *Include receipt photos and invoices* to put the files in it too (the file gets larger); without it, a restore keeps the list of receipts but not the files. **Restore** loads it into an empty add-on, or adds only the records that are missing. The current database is copied to `backups/` first.
