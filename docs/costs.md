# Cost model

All amounts are calculated by the add-on's **ledger**. This page defines every formula, so that each number in the GUI can be explained and reproduced.

## Cost categories

| Category | Comes from |
|---|---|
| **Electricity** | Home and public charge sessions, consumed through trips and idle records |
| **Fuel** | Refuels, consumed through trips and idle records |
| **Maintenance** | Maintenance records |
| **Other** | One-off and recurring expenses, optional depreciation |

**Energy cost** is electricity plus fuel. **Total cost** is all four categories.

## Price of each purchase

What you *bought* (charging, refuel) is priced first. What you *used* (trips) is priced from that, via the cost basis below.

### Home charge session

```
cost = Σ  Δkwh_i × price(t_i)        for every counter increase i during the session
avg_price = cost / energy_kwh
```

- `price(t_i)` is the charger's price entity state at that moment. When the entity is unavailable, the fixed charger price is used, and after that the add-on's fallback electricity price. The source used is stored per sample.
- **Your corrections** win over everything:
  - *€/kWh*: `cost = energy_kwh × price`.
  - *Total*: `cost = total`.
  - *Free*: `cost = 0`.

  The original automatic cost stays visible as *auto*.

### Public charge

`cost = energy_kwh × price_per_kwh + session_fee`, or the *total* you entered. `energy_kwh` is what you enter from the charge receipt. For detected sessions it starts as the estimate `Δbattery% × kwh_per_pct`.

### Refuel

Two of `litres`, `price_per_l` and `total` are given, and the third is calculated:

- `total = litres × price_per_l`
- `price_per_l = total / litres`

For a detected refuel, the suggested `price_per_l` comes from the fuel price entity or the previous refuel. It stays marked *estimated* until you confirm it.

## Before the first trip

Without trips there is nothing to spread energy over. Charges and refuels are therefore counted on a **purchase basis**, in the period they happened. A running session counts with its energy and cost so far. This stays the method for manual vehicles such as the VW Up.

From a vehicle's **first trip** on, the battery and tank cost basis below takes over: charges and refuels fill the pools, and trips and idle records are what costs money. Purchases before the first trip keep counting on purchase basis, so nothing is counted twice, except possibly the energy that was still on board at the switch (it is valued at the default prices when it is used).

## Battery and tank cost basis

A car stores energy you paid for at different prices. AutoLedger keeps two *pools* per vehicle, each with a **weighted average cost**.

| Pool | Content | Unit |
|---|---|---|
| Battery | Energy drawn from the wall (or public charger) | kWh |
| Tank | Fuel | L |

The ledger replays all records of a vehicle in time order:

```
on charge (kwh, cost):     pool_kwh  += kwh         pool_cost  += cost
on refuel (litres, cost):  tank_l    += litres      tank_cost  += cost

avg_kwh_price = pool_cost / pool_kwh            avg_l_price = tank_cost / tank_l

on trip or idle (kwh_used, l_used):
    electricity_cost = max(kwh_used, 0) × avg_kwh_price
    fuel_cost        = l_used × avg_l_price
    pool_kwh  -= max(kwh_used, 0)          pool_cost -= electricity_cost
    tank_l    -= l_used                    tank_cost -= fuel_cost
```

- **Starting state.** At the first trip, the battery (`battery_start_pct × kwh_per_pct`) and the tank (`fuel_start_l`) are valued at the default prices: the fallback electricity price, and the last refuel price before the first trip (else the default fuel price).
- **Engine-charged battery** (PHEV, `kwh_used < 0` during a trip): the kWh go into the pool at **€0**. Their cost is already counted as fuel on that same trip, so this avoids counting it twice.
- **Pools never go negative.** If sensor noise would push a pool below 0, it is clamped at 0. The difference is booked at the default price and noted in the trip's explanation.
- **Order.** Use and purchases are replayed by time. A trip and a refuel seen in the same car report count the trip first, because the refuel came at its end.
- **Recalculated on every read.** Costs are not stored: each list or summary replays the vehicle's records, so an edited charge price changes every later trip at once.
- **Why a pool, not "the last charge price"?** Your 0.19 €/kWh home electricity and an occasional 0.59 €/kWh fast charge then blend in proportion. This matches what the energy in the battery actually cost.

## kWh per percent

Trips use battery %, while charges are measured in kWh from the wall. The conversion factor `kwh_per_pct` therefore means *wall kWh needed for 1 % of battery*. It includes charging losses, so trip energy is valued at what you actually paid for.

- **Learned automatically** from home sessions with known battery % at start and end, and at least 20 % added:
  `kwh_per_pct = median over the last 10 sessions of (energy_kwh / (soc_end − soc_start))`
  It needs 3 such sessions. A session that gives less than 0.6× or more than 1.6× the capacity-based value is a bad reading and is skipped.
- **Until enough sessions exist:** `usable_capacity_kwh / 100 / 0.90`, assuming 90 % charging efficiency.
- **You can set it yourself** on the Charging → Efficiency card (or the vehicle's *wall kWh per %*). A manual value disables learning.
- Each trip uses the learned factor of the sessions finished before it, so learning never rewrites old trips. A manual value applies to all trips.

## Fuel reconciliation

Fuel level sensors are noisy: ±0.5 L from temperature, slope and fuel sloshing. A short PHEV trip often shows −0.4 L, or even +0.2 L.

### Fuel gauge noise

Between two refuels the tank can only go down, so every car report is a noisy reading of a falling level.

1. The tank level at the start and end of every trip and idle record is collected, in time order, and split into stretches at every refuel (and at any rise of 3 L or more, in case a refuel record was deleted).
2. Per stretch, the closest **non-increasing** line through those readings is fitted (least squares, *pool adjacent violators*).
3. A trip's **provisional** litres are the drop of that line over the trip, not the raw drop of the gauge. A trip that spans a refuel gets 0 until the next full tank, because its use is hidden in the refuel's estimate.
4. Costs are replayed on every request, so each new report re-fits the line. A dip that comes back is returned bit by bit.

Example, 2 Nov: the gauge goes 16.4 → 16.0 → 16.4 L over two trips without a refuel. The raw drops are 0.4 and 0 L. The smoothed line is 16.4 → 16.2 → 16.2, so trip 1 gets 0.2 L. After two more reports at 16.4 L it gets 0.1 L. Noise no longer adds up: 16.4 → 16.0 → 16.4 → 16.0 → 16.4 → 16.0 counts 0.4 L in total, not 1.2 L. Real use (16.4 → 16.0 → 15.6) is kept as measured.

Litres you entered yourself are not smoothed. The trip details show the gauge litres next to the costed litres.

### Correction at a full tank

1. At every **full-tank refuel**, the true use since the previous full tank is known: `litres_used = sum of litres refuelled in between, including this refuel`.
2. The difference between true use and the sum of provisional litres is **spread over those trips in proportion to their provisional litres**, so a PHEV trip that ran on electricity stays at 0. Only when no trip in between shows any fuel use is it spread by distance. Trip fuel becomes *reconciled* (a ✓ badge in the GUI) and costs are recalculated. Idle litres and litres you entered yourself stay as they are.
3. This only happens when both refuels have an odometer value and the trips cover at least 80 % of the km in between. Otherwise drives are missing (HA was down) and their fuel would land on the trips that were recorded. A full tank before the first trip is a valid start.

When no full-tank refuels are logged, the values stay provisional. Totals over longer periods are still accurate, because the tank level itself is measured.

## Consumption figures

| Figure | Formula |
|---|---|
| Electric consumption | `Σ trip kWh / Σ trip km × 100` → kWh/100 km |
| Fuel consumption (connected car) | `Σ trip L / Σ trip km × 100` → L/100 km, reconciled values where available |
| Fuel consumption (manual car) | Full-to-full: litres refuelled since the previous full tank / km since then × 100 |
| Electric share (PHEV) | Share of trip km where `fuel_l` < 0.5 L per 10 km. This is an estimate and is labelled as such. |
| Fuel consumption (connected car) and energy €/km | Trip-based only for periods that lie fully after the first trip; otherwise the full-to-full and odometer figures are used. |
| Energy €/km | `(electricity + fuel cost of trips) / trip km` |
| Total €/km | `all costs in period / km in period` |

Idle records (climate, standby) count in energy cost but **not** in consumption per 100 km. They appear as their own line, *"climate & standby"*.

## Distance for manual vehicles

A manual vehicle has no trips, so km per period comes from odometer values. Those come from odometer readings and from the odometer field of refuels and maintenance records.

- Between two known values, km are spread **evenly over time**, by linear interpolation.
- After the last known value, the period shows *"not yet known"* rather than an estimate.

Example: 41 230 km on 1 Oct and 41 890 km on 31 Oct gives 660 km in October. When the next reading only comes on 20 Nov, November's km stay partial until then.

## Fuel cost for manual vehicles

A manual vehicle has no trips to spread fuel over. Its fuel cost is therefore counted on a **purchase basis**: a refuel's total falls in the period in which you bought it. Over a month this is lumpy, since one refuel may cover several weeks of driving. Over a quarter or a year it is exact. For that reason the overview shows €/km over the last 12 months next to the selected period.

## Recurring expenses and depreciation

- A recurring expense of amount *A* with interval *n* months adds `A / n` to every month in its active range. A yearly € 600 insurance becomes € 50 per month.
- Depreciation: `(purchase_price − expected_resale) / months_between(purchase_date, expected_resale_date)` per month. It is off by default and can be switched on per vehicle.

## Recalculation

- Nothing derived is stored: every request replays the vehicle's records (a few thousand per year take milliseconds), so any change to a charge, refuel or trip is reflected everywhere at once. *(A per-record cache of the cost-basis state can follow when histories grow large.)*
- Each trip and idle record in the API carries a `costing` block with the full calculation: factor and its source, kWh, kWh price, provisional and reconciled litres, litre price and notes. The Trips page shows it under **Details**.

## Worked example (Lynk & Co, 2 Nov 2026)

The car reported this segment at 13:42:

| | Before | After | Δ |
|---|---|---|---|
| Trip meter 2 | 1375.7 km | 1382.0 km | **6.3 km** |
| Battery | 78.0 % | 66.5 % | −11.5 % |
| Fuel | 16.4 L | 16.0 L | −0.4 L (provisional) |
| Place | Home | Home | round trip |

Assume `kwh_per_pct` = 0.165 (16.5 kWh from the wall for a full charge), a battery pool average of €0.19/kWh (home charging at the Quatt price) and a tank average of €2.00/L:

```
electricity  11.5 × 0.165 = 1.90 kWh × 0.19 = € 0.36
fuel         0.4 L × 2.00                   = € 0.80   (provisional until the next full tank)
trip cost                                     € 1.16   → € 0.18 / km
```

If the next report shows 16.4 L again without a refuel, the [noise smoothing](#fuel-gauge-noise) lowers this trip to 0.2 L (€ 0.40), and further reports at 16.4 L lower it more.
