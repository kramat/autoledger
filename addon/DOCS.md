# AutoLedger

AutoLedger keeps the books for your cars: every trip, charge, refuel, maintenance entry and other cost, with km, kWh, litres, € and €/km per car or for all cars together. It works on its own for cars you log by hand; with the **AutoLedger Collector** integration, drives, home charging, refuels and public charging of a connected car are recorded automatically.

## Getting started

1. Start the add-on and open **AutoLedger** from the sidebar.
2. Go to **Vehicles → Add vehicle**. For *Tracking starts on*, use the earliest date you have data for, together with the odometer value on that date. Reports start there.
3. Check the currency and default prices under **Settings**.
4. Add refuels under **Fuel**. Enter two of litres, total and price per litre; the third is calculated. Tick *Filled the tank completely* when you filled up: L/100 km is calculated from one full tank to the next.
5. Add maintenance under **Maintenance**, and insurance, road tax, parking and so on under **Costs**. A recurring cost (for example a yearly insurance) is spread over the months it covers. One bill for several cars, such as road assistance, is entered once with *For: Shared*: it is split equally, by km driven, or with fixed percentages.

Older data can be entered with its original date, or imported from a spreadsheet (see [Data and backups](#data-and-backups)).

## Automatic tracking with the Collector

Install **AutoLedger Collector** through HACS (custom repository `https://github.com/kramat/autoledger`, category *Integration*) and restart Home Assistant. It finds this add-on by itself: confirm the *AutoLedger discovered* notification. Then, on the integration page:

- **Add vehicle** links an AutoLedger vehicle to its car entities: the odometer, and if you have them the trip meter, battery and fuel level, location and the car's report time. The next step suggests the entities of the same device.
- **Add home charger** links your charger's kWh counter and, optionally, an electricity price sensor. Every session is priced per kWh at the price of that moment.
- *Snapshot boost* (in the vehicle's settings) asks the car's integration for fresh data when the home charger starts or stops and when someone leaves or comes home, so a cloud car's trips start and end at the right time.

Right after installing, run the `autoledger.backfill` action (**Tools → Actions**, *Developer tools* in older versions) with a start date to recover the last days from Home Assistant's history.

Each car also gets sensors in Home Assistant, such as the cost this month, cost per km, last trip and next maintenance.

## The review inbox

Whatever the Collector is not sure about lands under **Review**: a refuel that needs the price you paid, a charge away from home, a battery that went up while driving (public charge or charged by the engine?) or a home charge without a car. Each item has quick actions; editing the record also confirms it. The count is the sensor `sensor.autoledger_items_to_review`.

## How km are counted

Distance comes from odometer values: the vehicle's starting value, odometer readings, and the odometer of refuels and maintenance. Between two values the km are spread evenly over time. After the last known value there is no estimate, and the overview tells you how far the data goes. A value lower than an earlier one is ignored, so check the starting odometer when the km look too low.

For a car in the Collector, every drive also becomes a **trip** with km, kWh, litres and cost on the **Trips** page, where you can split a trip that covered several drives or merge two.

## Maintenance reminders

Under **Maintenance → Schedules**, add what recurs: *Service every 12 months or 15 000 km*, *APK every year*. Enter when it was last done; after that, every maintenance entry of the same category (or linked to the schedule) moves it forward by itself. **Log as done** fills in the entry for you. A schedule is *due soon* within its reminder window (default 30 days or 1 000 km) and *overdue* after the date or km. Km-based dates are estimated from how much the car drove in the last 90 days.

With the Collector, each car gets `sensor.<car>_next_maintenance` (days to the next due item), `binary_sensor.<car>_maintenance_due`, and the event `autoledger_maintenance_due` for your own notifications.

## Reports

**Reports** shows a calendar year (or any period) per month, quarter or year, with the cars side by side. *Per year* figures scale the period to 365 days, so a car with a shorter history compares fairly. Below that are monthly trends of € per km and consumption, and consumption per season. **Export XLSX / CSV** downloads the report.

## Receipts and depreciation

**Receipts.** In the dialog of a refuel, a maintenance entry or a cost, **Add photo or PDF** attaches a receipt or invoice. On a phone this offers the camera. Photos over 1.5 MB are made smaller (2000 px JPEG) before they are uploaded; PDFs and HEIC photos are kept as they are, up to 20 MB. A 📎 in the table marks records with a receipt.

**Depreciation.** On **Vehicles**, fill in the purchase price and date, the expected resale value and date, and tick *Count depreciation in the costs*. The loss of value (purchase − resale) is spread evenly over the months in between and counted from the vehicle's tracking start up to today, as a separate *Depreciation* line in the overview and the reports. It is included in the total cost and €/km, so switch it off when you only want running costs.

## Language

AutoLedger speaks English and Dutch. Under **Settings → General → Language**, *Automatic* (the default) follows the language of each phone or browser; *English* and *Nederlands* fix it for everyone. The Collector follows your Home Assistant profile language.

## Data and backups

Everything is stored in the add-on's data folder and included in Home Assistant backups. Before each database upgrade, the add-on also makes a copy in `backups/` inside that folder.

Under **Settings**:

- **Export**: all records as one Excel workbook, or one CSV per type.
- **Import CSV**: refuels, maintenance, odometer readings or one-off costs from a spreadsheet. The preview shows how each row is read (columns, decimal comma, day-first dates) before anything is saved, and rows that are already there are skipped.
- **Backup**: a JSON file with everything, to move to another installation. Tick *Include receipt photos and invoices* to put the files in it too (the file gets larger); without it, a restore keeps the list of receipts but not the files. **Restore** loads it into an empty add-on, or adds only the records that are missing. The current database is copied to `backups/` first.

## Options

| Option | Meaning |
|---|---|
| Log level | How much the add-on writes to its log |
| Network: port 8099 | Leave empty to keep the API internal. Set a port to use the API from your own scripts; send the token from **Settings** as `Authorization: Bearer <token>`. |
