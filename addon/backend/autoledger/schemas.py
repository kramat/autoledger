"""Pydantic models for the REST API.

Each resource has an ``*In`` model (create, and full validation of a PATCH after
merging it onto the stored record) and an ``*Out`` model.
"""

import datetime as dt
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field, model_validator

VehicleType = Literal["ICE", "PHEV", "BEV"]
FuelType = Literal["petrol", "diesel", "lpg", "none"]
Tracking = Literal["manual", "collector"]
MaintenanceCategory = Literal[
    "service", "inspection", "tyres", "repair", "battery", "cleaning", "other"
]
ExpenseCategory = Literal[
    "insurance", "road_tax", "parking", "tolls", "car_wash", "fine",
    "accessories", "lease", "subscription", "other",
]
Recurrence = Literal["monthly", "quarterly", "yearly"]


class InModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int
    deleted_at: dt.datetime | None = None


class AutoOut(BaseModel):
    source: str
    status: str
    locked_fields: list[str] = []


# --- Vehicles -------------------------------------------------------------


class VehicleIn(InModel):
    name: str = Field(min_length=1, max_length=80)
    plate: str | None = Field(None, max_length=20)
    make: str | None = Field(None, max_length=40)
    model: str | None = Field(None, max_length=40)
    year: int | None = Field(None, ge=1900, le=2100)
    type: VehicleType = "ICE"
    fuel_type: FuelType = "petrol"
    tank_l: float | None = Field(None, gt=0)
    battery_usable_kwh: float | None = Field(None, gt=0)
    tracking: Tracking = "manual"
    start_odometer_km: float = Field(ge=0)
    start_date: dt.date
    purchase_price: float | None = Field(None, ge=0)
    purchase_date: dt.date | None = None
    kwh_per_pct: float | None = Field(None, gt=0, le=2)
    color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    note: str | None = None

    @model_validator(mode="after")
    def _check_type(self) -> "VehicleIn":
        if self.type == "BEV" and self.fuel_type != "none":
            self.fuel_type = "none"
        if self.type != "BEV" and self.fuel_type == "none":
            raise ValueError("A vehicle with an engine needs a fuel type")
        return self


class VehicleOut(VehicleIn, RecordOut):
    model_config = ConfigDict(from_attributes=True)

    archived_at: dt.datetime | None = None


# --- Refuels --------------------------------------------------------------


class RefuelIn(InModel):
    vehicle_id: str
    ts: AwareDatetime
    odometer_km: float | None = Field(None, ge=0)
    litres: float | None = Field(None, gt=0)
    price_per_l: float | None = Field(None, gt=0)
    total: float | None = Field(None, ge=0)
    full_tank: bool = True
    station: str | None = Field(None, max_length=120)
    note: str | None = None

    @model_validator(mode="after")
    def _derive(self) -> "RefuelIn":
        """Two of litres, price_per_l and total are enough; the third is calculated."""
        litres, price, total = self.litres, self.price_per_l, self.total
        given = sum(v is not None for v in (litres, price, total))
        if given < 2:
            raise ValueError("Give at least two of litres, price_per_l and total")
        if litres is None:
            self.litres = round(total / price, 3)
        elif price is None:
            self.price_per_l = round(total / litres, 4)
        elif total is None:
            self.total = round(litres * price, 2)
        elif abs(litres * price - total) > max(0.05, 0.01 * total):
            raise ValueError("litres × price_per_l does not match total")
        return self


class RefuelOut(RefuelIn, RecordOut, AutoOut):
    model_config = ConfigDict(from_attributes=True)

    litres: float
    price_per_l: float
    total: float
    # Filled in on list responses: consumption of the full-to-full interval ending here.
    interval_km: float | None = None
    l_per_100km: float | None = None


# --- Odometer readings ----------------------------------------------------


class OdometerIn(InModel):
    vehicle_id: str
    ts: AwareDatetime
    odometer_km: float = Field(ge=0)
    note: str | None = None


class OdometerOut(OdometerIn, RecordOut, AutoOut):
    model_config = ConfigDict(from_attributes=True)


# --- Maintenance ----------------------------------------------------------


class MaintenanceIn(InModel):
    vehicle_id: str
    date: dt.date
    odometer_km: float | None = Field(None, ge=0)
    category: MaintenanceCategory = "service"
    description: str = Field(min_length=1, max_length=200)
    garage: str | None = Field(None, max_length=120)
    cost: float = Field(0, ge=0)
    schedule_id: str | None = None
    note: str | None = None


class MaintenanceOut(MaintenanceIn, RecordOut):
    model_config = ConfigDict(from_attributes=True)


class ScheduleIn(InModel):
    vehicle_id: str
    name: str = Field(min_length=1, max_length=80)
    category: MaintenanceCategory | None = None
    interval_months: int | None = Field(None, ge=1, le=240)
    interval_km: float | None = Field(None, gt=0)
    last_done_date: dt.date | None = None
    last_done_km: float | None = Field(None, ge=0)
    remind_before_days: int = Field(30, ge=0, le=365)
    remind_before_km: float = Field(1000, ge=0)
    active: bool = True
    note: str | None = None

    @model_validator(mode="after")
    def _check_interval(self) -> "ScheduleIn":
        if self.interval_months is None and self.interval_km is None:
            raise ValueError("Give an interval in months, in km, or both")
        return self


class ScheduleOut(ScheduleIn, RecordOut):
    model_config = ConfigDict(from_attributes=True)

    # Filled in on list responses (docs/api.md#resources).
    due: dict | None = None


class CarServiceOut(BaseModel):
    """The car's own service countdown, as last reported by the collector."""

    days_to_service: float | None = None
    distance_to_service: float | None = None
    reported_at: dt.datetime
    odometer_km: float | None = None
    # The countdown turned into a date and an odometer value.
    due_date: dt.date | None = None
    due_km: float | None = None


# --- Expenses -------------------------------------------------------------


class ExpenseIn(InModel):
    vehicle_id: str
    category: ExpenseCategory = "other"
    amount: float = Field(ge=0)
    date: dt.date
    recurrence: Recurrence | None = None
    end_date: dt.date | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> "ExpenseIn":
        if self.end_date is not None:
            if self.recurrence is None:
                raise ValueError("end_date is only used for recurring expenses")
            if self.end_date < self.date:
                raise ValueError("end_date must be on or after date")
        return self


class ExpenseOut(ExpenseIn, RecordOut):
    model_config = ConfigDict(from_attributes=True)


# --- Charging -------------------------------------------------------------

ChargeKind = Literal["home", "public", "manual"]
PriceMode = Literal["samples", "per_kwh", "total", "free"]


class ChargeIn(InModel):
    vehicle_id: str | None = None
    kind: ChargeKind = "public"
    start_ts: AwareDatetime
    end_ts: AwareDatetime | None = None
    energy_kwh: float = Field(ge=0)
    price_mode: PriceMode = "per_kwh"
    price_per_kwh: float | None = Field(None, ge=0)
    price_total: float | None = Field(None, ge=0)
    session_fee: float | None = Field(None, ge=0)
    soc_start: float | None = Field(None, ge=0, le=100)
    soc_end: float | None = Field(None, ge=0, le=100)
    address: str | None = Field(None, max_length=200)
    provider: str | None = Field(None, max_length=80)
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "ChargeIn":
        if self.end_ts is not None and self.end_ts < self.start_ts:
            raise ValueError("The end must be after the start")
        if self.price_mode == "per_kwh" and self.price_per_kwh is None:
            raise ValueError("Give a price per kWh, or choose another price mode")
        if self.price_mode == "total" and self.price_total is None:
            raise ValueError("Give the total amount, or choose another price mode")
        if self.price_mode == "samples" and self.kind != "home":
            raise ValueError("Live pricing is only available for home charging")
        if self.kind != "home" and self.vehicle_id is None:
            raise ValueError("Choose a vehicle")
        return self


class ChargeOut(ChargeIn, RecordOut, AutoOut):
    model_config = ConfigDict(from_attributes=True)

    session_key: str | None = None
    charger_name: str | None = None
    is_open: bool
    energy_estimated: bool
    auto_cost: float | None = None
    cost: float
    lat: float | None = None
    lon: float | None = None

    @computed_field
    @property
    def avg_price(self) -> float | None:
        return self.cost / self.energy_kwh if self.energy_kwh else None


# --- Trips and idle records -----------------------------------------------

TripKind = Literal["one_way", "round_trip"]


class TripIn(InModel):
    vehicle_id: str
    start_ts: AwareDatetime
    start_ts_estimated: bool = False
    end_ts: AwareDatetime
    start_address: str | None = Field(None, max_length=200)
    start_zone: str | None = Field(None, max_length=80)
    end_address: str | None = Field(None, max_length=200)
    end_zone: str | None = Field(None, max_length=80)
    kind: TripKind = "one_way"
    distance_km: float = Field(ge=0)
    battery_start_pct: float | None = Field(None, ge=0, le=100)
    battery_end_pct: float | None = Field(None, ge=0, le=100)
    battery_used_pct: float | None = Field(None, ge=-100, le=200)
    energy_kwh: float | None = Field(None, ge=-50, le=500)
    fuel_l: float = Field(0, ge=0)
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> "TripIn":
        if self.end_ts < self.start_ts:
            raise ValueError("The end must be after the start")
        if self.battery_used_pct is None and None not in (self.battery_start_pct, self.battery_end_pct):
            self.battery_used_pct = round(self.battery_start_pct - self.battery_end_pct, 2)
        return self


class TripCostOut(BaseModel):
    energy_kwh: float
    kwh_per_pct: float | None = None
    factor_mode: str | None = None
    kwh_price: float | None = None
    electricity_cost: float
    fuel_l_measured: float
    fuel_l_provisional: float
    fuel_l: float
    fuel_reconciled: bool
    l_price: float | None = None
    fuel_cost: float
    cost: float
    notes: list[str] = []


class TripOut(TripIn, RecordOut, AutoOut):
    model_config = ConfigDict(from_attributes=True)

    start_lat: float | None = None
    start_lon: float | None = None
    end_lat: float | None = None
    end_lon: float | None = None
    odometer_start: float | None = None
    odometer_end: float | None = None
    distance_source: str
    charged_kwh: float = 0
    fuel_start_l: float | None = None
    fuel_end_l: float | None = None
    origin: dict = {}
    # Filled in on responses: how the ledger costed this trip.
    costing: TripCostOut | None = None


class IdleIn(InModel):
    vehicle_id: str
    start_ts: AwareDatetime
    end_ts: AwareDatetime
    zone: str | None = Field(None, max_length=80)
    battery_start_pct: float | None = Field(None, ge=0, le=100)
    battery_end_pct: float | None = Field(None, ge=0, le=100)
    battery_used_pct: float | None = Field(None, ge=-100, le=200)
    energy_kwh: float | None = Field(None, ge=-50, le=500)
    fuel_l: float = Field(0, ge=0)
    note: str | None = None


class IdleOut(IdleIn, RecordOut, AutoOut):
    model_config = ConfigDict(from_attributes=True)

    costing: TripCostOut | None = None


class SplitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at_km: float = Field(gt=0)
    at_ts: AwareDatetime
    address: str | None = Field(None, max_length=200)


class MergeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(min_length=2, max_length=2)


# --- Review inbox ---------------------------------------------------------


class ReviewItemOut(RecordOut):
    vehicle_id: str | None
    record_type: str | None
    record_id: str | None
    reason: str
    details: dict
    resolved_at: dt.datetime | None = None
    resolution: dict | None = None
    record: dict | None = None  # current state of the record, for quick actions


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["update", "accept", "delete", "dismiss"]
    values: dict = {}


# --- Ingest (collector events) --------------------------------------------


class Place(BaseModel):
    lat: float | None = None
    lon: float | None = None
    address: str | None = None
    zone: str | None = None


class IngestEventIn(BaseModel):
    uuid: str = Field(min_length=8, max_length=36)
    type: str
    vehicle_id: str | None = None
    source: str = "collector"
    collector_version: str | None = None
    occurred_at: AwareDatetime
    payload: dict = {}


class IngestBatch(BaseModel):
    events: list[IngestEventIn] = Field(max_length=100)


class PriceSample(BaseModel):
    ts: AwareDatetime
    kwh: float = Field(ge=0)
    price: float = Field(ge=0)
    source: str = "entity"


class ChargePayload(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    charger_key: str | None = None
    charger_name: str | None = None
    start_ts: AwareDatetime
    end_ts: AwareDatetime | None = None
    energy_kwh: float = Field(ge=0)
    cost: float | None = Field(None, ge=0)
    price_samples: list[PriceSample] | None = None
    soc_start: float | None = Field(None, ge=0, le=100)
    soc_end: float | None = Field(None, ge=0, le=100)


class SocUpdatePayload(BaseModel):
    session_id: str
    soc_start: float | None = Field(None, ge=0, le=100)
    soc_end: float | None = Field(None, ge=0, le=100)


class ExternalChargePayload(BaseModel):
    window_start: AwareDatetime
    window_end: AwareDatetime
    place: Place = Place()
    battery_start_pct: float = Field(ge=0, le=100)
    battery_end_pct: float = Field(ge=0, le=100)
    energy_kwh_estimated: float = Field(ge=0)
    car_reported_charging: bool | None = None
    flags: list[str] = []


class RefuelPayload(BaseModel):
    ts: AwareDatetime
    place: Place = Place()
    odometer_km: float | None = Field(None, ge=0)
    fuel_start_l: float = Field(ge=0)
    fuel_end_l: float = Field(ge=0)
    litres_estimated: float = Field(gt=0)
    suggested_price_per_l: float | None = Field(None, gt=0)
    price_source: str | None = None


class OdometerPayload(BaseModel):
    ts: AwareDatetime
    odometer_km: float = Field(ge=0)


class TripPayload(BaseModel):
    start_ts: AwareDatetime
    start_ts_estimated: bool = True
    end_ts: AwareDatetime
    start: Place = Place()
    end: Place = Place()
    odometer_start: float | None = Field(None, ge=0)
    odometer_end: float | None = Field(None, ge=0)
    distance_km: float = Field(ge=0)
    distance_source: Literal["trip_meter", "odometer"] = "odometer"
    battery_start_pct: float | None = Field(None, ge=0, le=100)
    battery_end_pct: float | None = Field(None, ge=0, le=100)
    charged_kwh: float = Field(0, ge=0)  # charged within the same window (home counter or public estimate)
    fuel_start_l: float | None = Field(None, ge=0)
    fuel_end_l: float | None = Field(None, ge=0)
    kind: TripKind = "one_way"
    flags: list[str] = []


class ServiceStatusPayload(BaseModel):
    days_to_service: float | None = None
    distance_to_service: float | None = Field(None, description="km")
    odometer_km: float | None = None


class IdlePayload(BaseModel):
    start_ts: AwareDatetime
    end_ts: AwareDatetime
    zone: str | None = None
    battery_start_pct: float | None = Field(None, ge=0, le=100)
    battery_end_pct: float | None = Field(None, ge=0, le=100)
    fuel_start_l: float | None = Field(None, ge=0)
    fuel_end_l: float | None = Field(None, ge=0)


# --- Settings -------------------------------------------------------------


class FuelPrices(BaseModel):
    petrol: float = Field(2.00, gt=0)
    diesel: float = Field(1.75, gt=0)
    lpg: float = Field(0.90, gt=0)


class SettingsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field("EUR", pattern=r"^[A-Z]{3}$")
    electricity_price: float = Field(0.25, ge=0, description="Fallback €/kWh")
    public_charge_price: float = Field(0.59, ge=0, description="Default €/kWh for public charging")
    fuel_prices: FuelPrices = FuelPrices()


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
