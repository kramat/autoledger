"""Constants for the AutoLedger Collector."""

from datetime import timedelta

DOMAIN = "autoledger"
VERSION = "0.4.0"
API_VERSION = 1

CONF_URL = "url"
CONF_TOKEN = "token"

SUBENTRY_VEHICLE = "vehicle"
SUBENTRY_CHARGER = "charger"

# Vehicle subentry data
CONF_VEHICLE_ID = "vehicle_id"
CONF_VEHICLE = "vehicle"  # add-on vehicle values copied at setup; refreshed from every summary poll
VEHICLE_INFO_KEYS = ("type", "tank_l", "battery_usable_kwh", "kwh_per_pct", "name")
CONF_FUEL_UNIT = "fuel_unit"
CONF_THRESHOLDS = "thresholds"
CONF_EXTERNAL_CHARGE_MIN_PCT = "external_charge_min_pct"
CONF_REFUEL_MIN_L = "refuel_min_l"
CONF_MIN_TRIP_KM = "min_trip_km"
CONF_IDLE_MIN_PCT = "idle_min_pct"
CONF_IDLE_MIN_L = "idle_min_l"

ROLE_ODOMETER = "odometer"
ROLE_TRIP_METER = "trip_meter"
ROLE_BATTERY = "battery_level"
ROLE_FUEL = "fuel_level"
ROLE_TRACKER = "tracker"
ROLE_LATITUDE = "latitude"
ROLE_LONGITUDE = "longitude"
ROLE_ADDRESS = "address"
ROLE_CHARGING = "charging_state"
ROLE_PLUG = "plug_state"
ROLE_CAR_TIMESTAMP = "car_timestamp"
VEHICLE_ROLES = (
    ROLE_ODOMETER, ROLE_TRIP_METER, ROLE_BATTERY, ROLE_FUEL, ROLE_TRACKER, ROLE_LATITUDE, ROLE_LONGITUDE,
    ROLE_ADDRESS, ROLE_CHARGING, ROLE_PLUG, ROLE_CAR_TIMESTAMP,
)
# The car's own service countdown: read at each snapshot, but they do not trigger one.
ROLE_DAYS_TO_SERVICE = "days_to_service"
ROLE_DISTANCE_TO_SERVICE = "distance_to_service"
SERVICE_ROLES = (ROLE_DAYS_TO_SERVICE, ROLE_DISTANCE_TO_SERVICE)

# Charger subentry data
CONF_NAME = "name"
CONF_ENERGY = "energy"
CONF_POWER = "power"
CONF_SWITCH = "switch"
CONF_PRICE = "price"
CONF_FIXED_PRICE = "fixed_price"
CONF_CHARGER_VEHICLE = "vehicle_subentry"
CONF_ADVANCED = "advanced"
CONF_START_W = "start_w"
CONF_STOP_W = "stop_w"
CONF_MIN_SESSION_KWH = "min_session_kwh"

SNAPSHOT_DEBOUNCE = 30  # seconds without changes before a snapshot is taken
SUMMARY_INTERVAL = timedelta(minutes=5)
TICK_INTERVAL = timedelta(minutes=1)
OUTBOX_MAX = 10_000
OUTBOX_BATCH = 100
OUTBOX_RETRY = (10, 30, 120, 600)  # seconds
REPAIR_AFTER = timedelta(hours=24)

EVENT_CHARGE_COMPLETED = f"{DOMAIN}_charge_completed"
EVENT_REFUEL_DETECTED = f"{DOMAIN}_refuel_detected"
EVENT_REVIEW_NEEDED = f"{DOMAIN}_review_needed"
EVENT_TRIP_RECORDED = f"{DOMAIN}_trip_recorded"
EVENT_MAINTENANCE_DUE = f"{DOMAIN}_maintenance_due"

SIGNAL_CHARGER_UPDATE = f"{DOMAIN}_charger_update_{{}}"
