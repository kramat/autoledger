"""Pydantic models for the REST API.

Each resource has an ``*In`` model (create, and full validation of a PATCH after
merging it onto the stored record) and an ``*Out`` model.
"""

import datetime as dt
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

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
    note: str | None = None


class MaintenanceOut(MaintenanceIn, RecordOut):
    model_config = ConfigDict(from_attributes=True)


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
