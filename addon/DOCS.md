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

## Options

| Option | Meaning |
|---|---|
| Log level | How much the add-on writes to its log |
| Network: port 8099 | Leave empty to keep the API internal. Set a port to use the API from your own scripts; send the token from **Settings** as `Authorization: Bearer <token>`. |

## Data and backups

Everything is stored in the add-on's data folder and included in Home Assistant backups. Before each database upgrade, the add-on also makes a copy in `backups/` inside that folder.
