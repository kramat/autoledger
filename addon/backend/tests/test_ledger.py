from datetime import date, datetime

import pytest

from autoledger.ledger import (
    ExpenseData,
    MaintenanceData,
    OdoPoint,
    PeriodTotals,
    RefuelData,
    VehicleBook,
    build_odometer_points,
    distance_between,
    expense_in_range,
    fuel_intervals,
    month_ranges,
)

from .conftest import TZ


def at(day: str, hour: int = 0) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=TZ)


# --- Distance -------------------------------------------------------------


def test_distance_is_interpolated_between_points():
    points = [OdoPoint(at("2026-09-01"), 1000), OdoPoint(at("2026-10-01"), 1600)]
    assert distance_between(points, at("2026-09-01"), at("2026-09-16")) == pytest.approx(300)


def test_distance_is_not_extrapolated_after_last_point():
    points = [OdoPoint(at("2026-10-01"), 1000), OdoPoint(at("2026-10-11"), 1100)]
    assert distance_between(points, at("2026-10-01"), at("2026-11-01")) == pytest.approx(100)


def test_distance_across_dst_change_uses_real_elapsed_time():
    # 25 Oct 2026 has 25 hours in Amsterdam; the split must follow real time.
    points = [OdoPoint(at("2026-10-25"), 0), OdoPoint(at("2026-10-26"), 250)]
    assert distance_between(points, at("2026-10-25"), at("2026-10-25", 12)) == pytest.approx(130)


def test_odometer_points_going_backwards_are_dropped():
    points, dropped = build_odometer_points(
        [OdoPoint(at("2026-10-01"), 1000), OdoPoint(at("2026-10-05"), 990), OdoPoint(at("2026-10-10"), 1200)]
    )
    assert [p.km for p in points] == [1000, 1200]
    assert dropped == 1


# --- Fuel -----------------------------------------------------------------


def refuel(id_, day, litres, total, full=True, odo=None):
    return RefuelData(id_, at(day), litres, total, full, odo)


def test_full_to_full_includes_partial_refuels():
    intervals = fuel_intervals(
        [
            refuel("a", "2026-09-01", 30, 60, odo=41000),
            refuel("b", "2026-09-15", 10, 20, full=False, odo=41250),
            refuel("c", "2026-10-01", 30, 61, odo=41500),
        ]
    )
    assert len(intervals) == 1
    assert intervals[0].end_refuel_id == "c"
    assert intervals[0].litres == 40
    assert intervals[0].km == 500
    assert intervals[0].l_per_100km == pytest.approx(8.0)


def test_full_refuel_without_odometer_breaks_the_chain():
    intervals = fuel_intervals(
        [
            refuel("a", "2026-09-01", 30, 60, odo=41000),
            refuel("b", "2026-09-15", 20, 40),  # full, but odometer unknown
            refuel("c", "2026-10-01", 25, 50, odo=41800),
            refuel("d", "2026-10-20", 22, 44, odo=42200),
        ]
    )
    assert [(i.end_refuel_id, i.litres, i.km) for i in intervals] == [("d", 22, 400)]


def test_first_refuel_only_anchors():
    assert fuel_intervals([refuel("a", "2026-09-01", 30, 60, odo=41000)]) == []


# --- Expenses -------------------------------------------------------------

TODAY = date(2026, 11, 2)


def test_one_off_expense():
    expense = ExpenseData(date(2026, 10, 5), 25.0)
    assert expense_in_range(expense, date(2026, 10, 1), date(2026, 11, 1), TODAY) == 25
    assert expense_in_range(expense, date(2026, 11, 1), date(2026, 12, 1), TODAY) == 0


def test_yearly_expense_is_spread_per_month():
    insurance = ExpenseData(date(2026, 1, 1), 600.0, "yearly")
    assert expense_in_range(insurance, date(2026, 10, 1), date(2026, 11, 1), TODAY) == pytest.approx(50)
    # Jan to Oct complete, November counts too (it is the current month).
    assert expense_in_range(insurance, date(2026, 1, 1), date(2027, 1, 1), TODAY) == pytest.approx(550)


def test_recurring_expense_is_prorated_for_partial_months():
    tax = ExpenseData(date(2026, 1, 1), 93.0, "quarterly")  # 31 per month
    october_first_half = expense_in_range(tax, date(2026, 10, 1), date(2026, 10, 16), TODAY)
    assert october_first_half == pytest.approx(31 * 15 / 31)


def test_recurring_expense_stops_at_end_date():
    lease = ExpenseData(date(2026, 1, 1), 300.0, "monthly", end_date=date(2026, 3, 31))
    assert expense_in_range(lease, date(2026, 1, 1), date(2027, 1, 1), TODAY) == pytest.approx(900)


# --- Totals and book ------------------------------------------------------


def test_per_km_figures_need_distance():
    totals = PeriodTotals(km=0.4, fuel_cost=10)
    assert totals.energy_cost_per_km is None
    assert totals.total_cost_per_km is None


def test_totals_add_up():
    combined = PeriodTotals(km=100, fuel_cost=10, interval_l=6, interval_km=100) + PeriodTotals(
        km=300, fuel_cost=30, maintenance_cost=40, interval_l=12, interval_km=300
    )
    assert combined.km == 400
    assert combined.total_cost == 80
    assert combined.energy_cost_per_km == pytest.approx(0.1)
    assert combined.fuel_l_per_100km == pytest.approx(4.5)


def test_month_ranges():
    assert month_ranges(date(2026, 2, 10), 3) == [
        (date(2025, 12, 1), date(2026, 1, 1)),
        (date(2026, 1, 1), date(2026, 2, 1)),
        (date(2026, 2, 1), date(2026, 3, 1)),
    ]


def test_vehicle_book_period():
    book = VehicleBook(
        tz=TZ,
        today=TODAY,
        start_date=date(2026, 9, 1),
        start_odometer_km=41000,
        refuels=[
            refuel("a", "2026-09-01", 30, 60, odo=41000),
            refuel("b", "2026-10-01", 33, 66.33, odo=41600),
        ],
        maintenance=[MaintenanceData(date(2026, 10, 10), 250.0, odometer_km=41900)],
        expenses=[ExpenseData(date(2026, 1, 1), 600.0, "yearly")],
    )
    october = book.period(date(2026, 10, 1), date(2026, 11, 1))
    # 41600 on 1 Oct 00:00, 41900 on 10 Oct 12:00, no later point.
    assert october.km == pytest.approx(300)
    assert october.fuel_cost == pytest.approx(66.33)
    assert october.fuel_l_per_100km == pytest.approx(5.5)
    assert october.maintenance_cost == 250
    assert october.other_cost == pytest.approx(50)
    assert october.total_cost == pytest.approx(366.33)
    assert book.latest_odometer.km == 41900
