"""CSV import: column guessing and tolerant parsing of numbers, dates and flags.

Spreadsheets and other apps export in many shapes: semicolons, decimal commas,
day-first dates, Dutch headers. Everything here is pure, so the preview and the
import use exactly the same rules (docs/addon.md#settings).
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

MAX_ROWS = 20_000


@dataclass(frozen=True)
class Field:
    name: str
    kind: str  # datetime | date | number | text | flag | category
    required: bool = False
    synonyms: tuple[str, ...] = ()


_NOTE = Field("note", "text", synonyms=("note", "notes", "opmerking", "opmerkingen", "comment", "comments", "remark",
                                        "remarks", "memo"))
_ODOMETER = Field("odometer_km", "number", synonyms=("odometer", "odometerkm", "km", "mileage", "kilometerstand",
                                                     "kmstand", "odo", "stand", "tellerstand", "distance"))

FIELDS: dict[str, tuple[Field, ...]] = {
    "refuels": (
        Field("ts", "datetime", True, ("date", "datum", "datetime", "time", "tijd", "day", "when", "timestamp")),
        Field("litres", "number", synonyms=("litres", "liters", "liter", "litre", "l", "volume", "quantity",
                                            "fuel", "getankt", "hoeveelheid")),
        Field("price_per_l", "number", synonyms=("priceperl", "pricel", "priceperlitre", "priceperliter", "ppl",
                                                 "unitprice", "literprijs", "prijsperliter", "prijsl", "eurl")),
        Field("total", "number", synonyms=("total", "totaal", "cost", "costs", "kosten", "bedrag", "amount",
                                           "totalcost", "totalprice", "price", "prijs")),
        _ODOMETER,
        Field("full_tank", "flag", synonyms=("fulltank", "full", "vol", "volletank", "tankvol", "filled")),
        Field("station", "text", synonyms=("station", "location", "place", "tankstation", "locatie", "plaats",
                                           "gasstation")),
        _NOTE,
    ),
    "maintenance": (
        Field("date", "date", True, ("date", "datum", "day", "when")),
        _ODOMETER,
        Field("category", "category", synonyms=("category", "categorie", "type", "soort", "kind")),
        Field("description", "text", synonyms=("description", "omschrijving", "work", "item", "title",
                                                "werkzaamheden", "what")),
        Field("garage", "text", synonyms=("garage", "workshop", "shop", "dealer", "bedrijf")),
        Field("cost", "number", synonyms=("cost", "costs", "kosten", "bedrag", "amount", "total", "totaal",
                                          "price", "prijs")),
        _NOTE,
    ),
    "odometer-readings": (
        Field("ts", "datetime", True, ("date", "datum", "datetime", "time", "tijd", "day", "when", "timestamp")),
        Field("odometer_km", "number", True, _ODOMETER.synonyms),
        _NOTE,
    ),
    "expenses": (
        Field("date", "date", True, ("date", "datum", "day", "when")),
        Field("amount", "number", True, ("amount", "bedrag", "cost", "costs", "kosten", "total", "totaal",
                                         "price", "prijs")),
        Field("category", "category", synonyms=("category", "categorie", "type", "soort", "kind")),
        _NOTE,
    ),
}

# Words in a category cell -> AutoLedger category, per resource.
CATEGORY_WORDS = {
    "maintenance": {
        "service": ("service", "beurt", "onderhoud", "oil", "olie", "inspection service"),
        "inspection": ("apk", "mot", "inspection", "keuring", "tuv"),
        "tyres": ("tyre", "tire", "band", "banden", "wheel"),
        "repair": ("repair", "reparatie", "fix", "schade", "damage"),
        "battery": ("battery", "accu", "batterij"),
        "cleaning": ("clean", "wash", "was", "poets"),
    },
    "expenses": {
        "insurance": ("insurance", "verzekering"),
        "road_tax": ("road tax", "roadtax", "mrb", "wegenbelasting", "motorrijtuigenbelasting"),
        "parking": ("parking", "parkeren", "parkeer"),
        "tolls": ("toll", "tol", "vignet"),
        "car_wash": ("wash", "wasstraat", "carwash"),
        "fine": ("fine", "boete", "bekeuring"),
        "accessories": ("accessor", "accessoire"),
        "lease": ("lease",),
        "subscription": ("subscription", "abonnement"),
    },
}

_TRUE = {"1", "yes", "y", "true", "ja", "j", "x", "full", "vol", "waar", "✓", "✔"}
_FALSE = {"0", "no", "n", "false", "nee", "partial", "half", "deels", "onwaar", ""}


def normalise(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", header.lower().replace("€", "eur"))


def read_csv(content: str, delimiter: str | None = None) -> tuple[list[str], list[list[str]], str]:
    """Header, rows and the delimiter used (sniffed when not given)."""
    content = content.lstrip("﻿")
    if delimiter is None:
        sample = "\n".join(content.splitlines()[:20])
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return [], [], delimiter
    header = [cell.strip() for cell in rows[0]]
    return header, rows[1 : MAX_ROWS + 1], delimiter


def guess_mapping(resource: str, header: list[str]) -> dict[str, str]:
    """field -> column, by exact synonym first and then by a synonym inside the header."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    normalised = {column: normalise(column) for column in header}
    for exact in (True, False):
        for field in FIELDS[resource]:
            if field.name in mapping:
                continue
            for column, norm in normalised.items():
                if column in used or not norm:
                    continue
                hit = norm in field.synonyms if exact else any(len(s) > 2 and s in norm for s in field.synonyms)
                if hit:
                    mapping[field.name] = column
                    used.add(column)
                    break
    return mapping


_COMMA_DECIMAL = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d+$|^-?\d+,\d+$")
_POINT_DECIMAL = re.compile(r"^-?\d{1,3}(,\d{3})*\.\d+$|^-?\d+\.\d+$")


def _clean_number(text: str) -> str:
    return re.sub(r"[^\d,.\-]", "", text.replace("−", "-"))


def guess_decimal(cells: list[str]) -> str:
    comma = point = 0
    for cell in cells:
        value = _clean_number(cell)
        comma += bool(_COMMA_DECIMAL.match(value))
        point += bool(_POINT_DECIMAL.match(value))
    return "," if comma > point else "."


def parse_number(text: str, decimal: str) -> float | None:
    value = _clean_number(text)
    if not value or value in ("-", ".", ","):
        return None
    thousands = "." if decimal == "," else ","
    value = value.replace(thousands, "").replace(decimal, ".")
    try:
        return float(value)
    except ValueError as err:
        raise ValueError(f"{text!r} is not a number") from err


_DATE = re.compile(
    r"^\s*(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})(?:[ T,]+(\d{1,2})[:.](\d{2})(?:[:.](\d{2}))?)?"
)


def guess_date_order(cells: list[str]) -> str:
    """ymd when the year comes first; dmy unless a value only fits month-first."""
    first_big = second_big = year_first = False
    for cell in cells:
        match = _DATE.match(cell)
        if not match:
            continue
        a, b = int(match.group(1)), int(match.group(2))
        if len(match.group(1)) == 4:
            year_first = True
        elif a > 12:
            first_big = True
        elif b > 12:
            second_big = True
    if year_first:
        return "ymd"
    return "mdy" if second_big and not first_big else "dmy"


def parse_datetime(text: str, order: str) -> tuple[date, time | None]:
    """A date and, when the cell has one, a time of day."""
    match = _DATE.match(text)
    if not match:
        try:
            parsed = datetime.fromisoformat(text.strip())
            return parsed.date(), parsed.time() if "T" in text or ":" in text else None
        except ValueError:
            raise ValueError(f"{text!r} is not a date") from None
    p1, p2, p3 = (int(match.group(i)) for i in (1, 2, 3))
    if order == "ymd" or len(match.group(1)) == 4:
        year, month, day = p1, p2, p3
    elif order == "mdy":
        month, day, year = p1, p2, p3
    else:
        day, month, year = p1, p2, p3
    if year < 100:
        year += 2000 if year < 70 else 1900
    try:
        day_value = date(year, month, day)
    except ValueError:
        raise ValueError(f"{text!r} is not a valid date") from None
    if match.group(4) is None:
        return day_value, None
    return day_value, time(int(match.group(4)), int(match.group(5)), int(match.group(6) or 0))


def parse_flag(text: str) -> bool:
    value = text.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{text!r} is not yes or no")


def parse_category(resource: str, text: str) -> str:
    value = text.strip().lower()
    words = CATEGORY_WORDS.get(resource, {})
    if value.replace(" ", "_") in words:
        return value.replace(" ", "_")
    for category, hints in words.items():
        if any(hint in value for hint in hints):
            return category
    return "other"


@dataclass
class Options:
    decimal: str
    date_order: str
    tz: ZoneInfo


def convert_row(resource: str, cells: dict[str, str], options: Options) -> dict:
    """Mapped cells -> input values for the resource's schema. Raises ValueError."""
    values: dict = {}
    for field in FIELDS[resource]:
        text = (cells.get(field.name) or "").strip()
        if not text:
            if field.required:
                raise ValueError(f"{field.name} is empty")
            continue
        if field.kind == "number":
            values[field.name] = parse_number(text, options.decimal)
        elif field.kind == "flag":
            values[field.name] = parse_flag(text)
        elif field.kind == "category":
            values[field.name] = parse_category(resource, text)
        elif field.kind == "date":
            values[field.name] = parse_datetime(text, options.date_order)[0]
        elif field.kind == "datetime":
            day, at = parse_datetime(text, options.date_order)
            # A date without a time is placed at noon, so it stays on that day in any time zone.
            values[field.name] = datetime.combine(day, at or time(12), tzinfo=options.tz)
        else:
            values[field.name] = text
    if resource == "maintenance" and "description" not in values:
        values["description"] = cells.get("category", "").strip() or "Imported"
    return values
