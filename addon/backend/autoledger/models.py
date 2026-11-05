"""SQLAlchemy models. See docs/data-model.md."""

import datetime as dt

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .db import UTCDateTime, utcnow, uuid7


class Base(DeclarativeBase):
    pass


class RecordMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)


class AutoMixin:
    """Columns for records the collector can create (from M2 on)."""

    source: Mapped[str] = mapped_column(String(16), default="manual")
    status: Mapped[str] = mapped_column(String(16), default="ok")
    locked_fields: Mapped[list] = mapped_column(JSON, default=list)
    auto_values: Mapped[dict] = mapped_column(JSON, default=dict)
    ingest_uuid: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)


class Vehicle(RecordMixin, Base):
    __tablename__ = "vehicles"

    name: Mapped[str] = mapped_column(String(80))
    plate: Mapped[str | None] = mapped_column(String(20))
    make: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(40))
    year: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(8), default="ICE")
    fuel_type: Mapped[str] = mapped_column(String(10), default="petrol")
    tank_l: Mapped[float | None] = mapped_column(Float)
    battery_usable_kwh: Mapped[float | None] = mapped_column(Float)
    tracking: Mapped[str] = mapped_column(String(10), default="manual")
    start_odometer_km: Mapped[float] = mapped_column(Float)
    start_date: Mapped[dt.date] = mapped_column(Date)
    purchase_price: Mapped[float | None] = mapped_column(Float)
    purchase_date: Mapped[dt.date | None] = mapped_column(Date)
    # Straight-line depreciation from purchase to the expected resale (docs/costs.md#recurring-expenses-and-depreciation).
    resale_estimate: Mapped[float | None] = mapped_column(Float)
    resale_date: Mapped[dt.date | None] = mapped_column(Date)
    depreciation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Wall kWh per battery % (includes charging losses). None: derived from capacity.
    kwh_per_pct: Mapped[float | None] = mapped_column(Float)
    color: Mapped[str | None] = mapped_column(String(9))
    note: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Refuel(RecordMixin, AutoMixin, Base):
    __tablename__ = "refuels"
    __table_args__ = (Index("ix_refuels_vehicle_ts", "vehicle_id", "ts"),)

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    ts: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    odometer_km: Mapped[float | None] = mapped_column(Float)
    litres: Mapped[float] = mapped_column(Float)
    price_per_l: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    full_tank: Mapped[bool] = mapped_column(Boolean, default=True)
    station: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)


class OdometerReading(RecordMixin, AutoMixin, Base):
    __tablename__ = "odometer_readings"
    __table_args__ = (Index("ix_odometer_vehicle_ts", "vehicle_id", "ts"),)

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    ts: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    odometer_km: Mapped[float] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)


class MaintenanceRecord(RecordMixin, Base):
    __tablename__ = "maintenance_records"
    __table_args__ = (Index("ix_maintenance_vehicle_date", "vehicle_id", "date"),)

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    date: Mapped[dt.date] = mapped_column(Date)
    odometer_km: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200))
    garage: Mapped[str | None] = mapped_column(String(120))
    cost: Mapped[float] = mapped_column(Float, default=0)
    # The schedule this entry fulfils. None: it fulfils schedules of the same category.
    schedule_id: Mapped[str | None] = mapped_column(ForeignKey("maintenance_schedules.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text)


class MaintenanceSchedule(RecordMixin, Base):
    """A recurring maintenance item: every n months and/or every n km.

    ``last_done_*`` is the starting point the user entered. Maintenance records of
    the schedule (linked, or of the same category) move it forward when they are
    newer, so it never has to be updated by hand (docs/addon.md#maintenance).
    """

    __tablename__ = "maintenance_schedules"

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str | None] = mapped_column(String(20))
    interval_months: Mapped[int | None] = mapped_column(Integer)
    interval_km: Mapped[float | None] = mapped_column(Float)
    last_done_date: Mapped[dt.date | None] = mapped_column(Date)
    last_done_km: Mapped[float | None] = mapped_column(Float)
    remind_before_days: Mapped[int] = mapped_column(Integer, default=30)
    remind_before_km: Mapped[float] = mapped_column(Float, default=1000)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text)


class Expense(RecordMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_vehicle_date", "vehicle_id", "date"),)

    # NULL for a shared cost, which is split over split_vehicles (docs/costs.md#shared-costs).
    vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Float)
    date: Mapped[dt.date] = mapped_column(Date)
    recurrence: Mapped[str | None] = mapped_column(String(10))
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    split: Mapped[str | None] = mapped_column(String(8))  # None (one vehicle) | equal | km | percent
    split_vehicles: Mapped[list] = mapped_column(JSON, default=list)  # [{"vehicle_id", "percent"}]
    note: Mapped[str | None] = mapped_column(Text)


class Attachment(RecordMixin, Base):
    """A receipt photo or invoice of a refuel, maintenance entry or expense.

    The file is stored as ``<data dir>/attachments/<id>``; the row keeps its name and type.
    """

    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_record", "resource", "record_id"),)

    resource: Mapped[str] = mapped_column(String(24))  # refuels | maintenance | expenses
    record_id: Mapped[str] = mapped_column(String(36))
    filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))


class ChargeSession(RecordMixin, AutoMixin, Base):
    """A home (collector), public or manually entered charge."""

    __tablename__ = "charge_sessions"
    __table_args__ = (Index("ix_charges_vehicle_start", "vehicle_id", "start_ts"),)

    vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    session_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    kind: Mapped[str] = mapped_column(String(8), default="public")  # home | public | manual
    charger_key: Mapped[str | None] = mapped_column(String(64))
    charger_name: Mapped[str | None] = mapped_column(String(80))
    start_ts: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    end_ts: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(200))
    provider: Mapped[str | None] = mapped_column(String(80))
    energy_kwh: Mapped[float] = mapped_column(Float, default=0)
    energy_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    soc_start: Mapped[float | None] = mapped_column(Float)
    soc_end: Mapped[float | None] = mapped_column(Float)
    # samples: priced per kWh increment by the collector; per_kwh / total / free: set by the user.
    price_mode: Mapped[str] = mapped_column(String(8), default="per_kwh")
    price_per_kwh: Mapped[float | None] = mapped_column(Float)
    price_total: Mapped[float | None] = mapped_column(Float)
    session_fee: Mapped[float | None] = mapped_column(Float)
    auto_cost: Mapped[float | None] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float, default=0)
    price_samples: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str | None] = mapped_column(Text)


class Trip(RecordMixin, AutoMixin, Base):
    """A drive between two car reports (snapshot mode), or entered by hand.

    Energy and cost are not stored: the ledger derives them from the battery % used
    and the kWh-per-% factor at that moment, unless the user set ``energy_kwh``
    (then it is in ``locked_fields``).
    """

    __tablename__ = "trips"
    __table_args__ = (Index("ix_trips_vehicle_start", "vehicle_id", "start_ts"),)

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    start_ts: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    start_ts_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    end_ts: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lon: Mapped[float | None] = mapped_column(Float)
    start_address: Mapped[str | None] = mapped_column(String(200))
    start_zone: Mapped[str | None] = mapped_column(String(80))
    end_lat: Mapped[float | None] = mapped_column(Float)
    end_lon: Mapped[float | None] = mapped_column(Float)
    end_address: Mapped[str | None] = mapped_column(String(200))
    end_zone: Mapped[str | None] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(10), default="one_way")  # one_way | round_trip
    odometer_start: Mapped[float | None] = mapped_column(Float)
    odometer_end: Mapped[float | None] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    distance_source: Mapped[str] = mapped_column(String(12), default="manual")  # trip_meter | odometer | manual
    battery_start_pct: Mapped[float | None] = mapped_column(Float)
    battery_end_pct: Mapped[float | None] = mapped_column(Float)
    # Battery % that went down (start − end; summed for merged trips).
    battery_used_pct: Mapped[float | None] = mapped_column(Float)
    # Wall kWh charged within the same window (home counter or public estimate): also used on this trip.
    charged_kwh: Mapped[float] = mapped_column(Float, default=0)
    energy_kwh: Mapped[float | None] = mapped_column(Float)  # user value; None = derived
    fuel_start_l: Mapped[float | None] = mapped_column(Float)
    fuel_end_l: Mapped[float | None] = mapped_column(Float)
    fuel_l: Mapped[float] = mapped_column(Float, default=0)  # provisional litres, never negative
    origin: Mapped[dict] = mapped_column(JSON, default=dict)  # {"merged_from": [...]} | {"split_from": id}
    note: Mapped[str | None] = mapped_column(Text)


class IdleRecord(RecordMixin, AutoMixin, Base):
    """Energy used while parked (pre-climate, standby), costed but kept out of €/km."""

    __tablename__ = "idle_records"
    __table_args__ = (Index("ix_idle_vehicle_start", "vehicle_id", "start_ts"),)

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    start_ts: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    end_ts: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    zone: Mapped[str | None] = mapped_column(String(80))
    battery_start_pct: Mapped[float | None] = mapped_column(Float)
    battery_end_pct: Mapped[float | None] = mapped_column(Float)
    battery_used_pct: Mapped[float | None] = mapped_column(Float)
    energy_kwh: Mapped[float | None] = mapped_column(Float)  # user value; None = derived
    fuel_l: Mapped[float] = mapped_column(Float, default=0)
    note: Mapped[str | None] = mapped_column(Text)


class ReviewItem(RecordMixin, Base):
    """Something the system was not sure about and needs the user's input."""

    __tablename__ = "review_items"

    vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    record_type: Mapped[str | None] = mapped_column(String(20))  # refuel | charge
    record_id: Mapped[str | None] = mapped_column(String(36), index=True)
    reason: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolution: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class IngestEvent(Base):
    """Audit log of collector events; the uuid makes delivery idempotent."""

    __tablename__ = "ingest_events"

    uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(40))
    vehicle_id: Mapped[str | None] = mapped_column(String(36))
    occurred_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    received_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[str] = mapped_column(String(10))  # applied | rejected
    record_id: Mapped[str | None] = mapped_column(String(36))
    error: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | float | int | bool | None] = mapped_column(JSON)
