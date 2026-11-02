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
    note: Mapped[str | None] = mapped_column(Text)


class Expense(RecordMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_vehicle_date", "vehicle_id", "date"),)

    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"))
    category: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Float)
    date: Mapped[dt.date] = mapped_column(Date)
    recurrence: Mapped[str | None] = mapped_column(String(10))
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | float | int | bool | None] = mapped_column(JSON)
