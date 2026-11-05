"""Dutch versions of the messages the API returns.

The GUI sends ``Accept-Language`` with its interface language. Messages are
written in English in the code; this module translates them on the way out,
so every check keeps a single English source text and scripts get English.
"""

import re
from collections.abc import Mapping

SUPPORTED = ("en", "nl")


def language(accept_language: str | None) -> str:
    """The first supported language of an Accept-Language header, else English."""
    for part in (accept_language or "").split(","):
        tag = part.split(";")[0].strip().lower().split("-")[0]
        if tag in SUPPORTED:
            return tag
    return "en"


EXACT: dict[str, str] = {
    "'from' must be on or before 'to'": "De begindatum moet op of vóór de einddatum liggen",
    "A vehicle with an engine needs a fuel type": "Een voertuig met een motor heeft een brandstofsoort nodig",
    "Attach a photo (JPEG, PNG, WebP, HEIC) or a PDF": "Voeg een foto (JPEG, PNG, WebP, HEIC) of een pdf toe",
    "Attachment not found": "Bijlage niet gevonden",
    "Choose a vehicle": "Kies een voertuig",
    "Choose at least two vehicles to share the cost": "Kies minstens twee voertuigen om de kosten over te verdelen",
    "Give a percentage for every vehicle": "Vul voor elk voertuig een percentage in",
    "Choose two different trips of the same vehicle": "Kies twee verschillende ritten van hetzelfde voertuig",
    "Depreciation needs a purchase price, a purchase date and a resale date":
        "Voor afschrijving zijn een aankoopprijs, een aankoopdatum en een verkoopdatum nodig",
    "Give a price per kWh, or choose another price mode": "Vul een prijs per kWh in, of kies een andere prijsmethode",
    "Give an interval in months, in km, or both": "Vul een interval in maanden, in km of allebei in",
    "Give at least two of litres, price_per_l and total": "Vul minstens twee van liters, prijs per liter en totaal in",
    "Give the total amount, or choose another price mode": "Vul het totaalbedrag in, of kies een andere prijsmethode",
    "Live pricing is only available for home charging": "De actuele stroomprijs kan alleen bij thuisladen",
    "Must be between the start and the end of the trip": "Moet tussen het begin en het einde van de rit liggen",
    "Must be true or false": "Moet waar of onwaar zijn",
    "Naive datetimes are not allowed": "Een tijdstip moet een tijdzone hebben",
    "Only adjacent trips can be merged": "Alleen opeenvolgende ritten kunnen worden samengevoegd",
    "Pick a schedule of the same vehicle": "Kies een schema van hetzelfde voertuig",
    "Record not found": "Record niet gevonden",
    "The database already has vehicles. Restore with merge, or start from an empty add-on.":
        "De database heeft al voertuigen. Zet terug met samenvoegen, of begin met een lege add-on.",
    "The end must be after the start": "Het einde moet na het begin liggen",
    "The expected resale value is higher than the purchase price": "De verwachte verkoopwaarde is hoger dan de aankoopprijs",
    "The file is empty": "Het bestand is leeg",
    "The file is larger than 20 MB": "Het bestand is groter dan 20 MB",
    "The file of this attachment is missing (restored from a backup without files?)":
        "Het bestand van deze bijlage ontbreekt (teruggezet uit een back-up zonder bestanden?)",
    "The percentages must add up to 100": "De percentages moeten samen 100 zijn",
    "The resale date must be after the purchase date":"De verkoopdatum moet na de aankoopdatum liggen",
    "The token can only be managed from the AutoLedger panel": "Het token kan alleen in het AutoLedger-paneel worden beheerd",
    "This backup was made by a newer AutoLedger. Update the add-on first.":
        "Deze back-up is gemaakt met een nieuwere AutoLedger. Werk eerst de add-on bij.",
    "This is not an AutoLedger backup file": "Dit is geen back-upbestand van AutoLedger",
    "This item has no record to act on; dismiss it instead": "Bij dit item hoort geen record; negeer het in plaats daarvan",
    "This item is already resolved": "Dit item is al afgehandeld",
    "This record was changed in the meantime. Reload and try again.":
        "Dit record is intussen gewijzigd. Laad de pagina opnieuw en probeer het nog eens.",
    "Unknown vehicle": "Onbekend voertuig",
    "end_date is only used for recurring expenses": "Een einddatum is er alleen voor terugkerende kosten",
    "end_date must be on or after date": "De einddatum moet op of na de datum liggen",
    "litres × price_per_l does not match total": "Liters × prijs per liter komt niet overeen met het totaal",
    "Invalid value": "Ongeldige waarde",
}

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^Column (?P<column>\S+) is unknown to this version of AutoLedger$"),
     "Kolom {column} is onbekend in deze versie van AutoLedger"),
    (re.compile(r"^Must be between 0 and (?P<km>\S+) km$"), "Moet tussen 0 en {km} km liggen"),
    (re.compile(r"^The backup has conflicting rows in (?P<table>\S+)$"), "De back-up heeft tegenstrijdige rijen in {table}"),
    (re.compile(r"^Unknown export (?P<name>\S+)$"), "Onbekende export {name}"),
    (re.compile(r"^Unknown format (?P<name>.+)$"), "Onbekend formaat {name}"),
    (re.compile(r"^[\w-]+(?: item)? (?P<id>\S+) not found$"), "Record {id} niet gevonden"),
    (re.compile(r"^(?P<field>\w+) is empty$"), "{field} is leeg"),
    (re.compile(r"^(?P<text>.+) is not a number$"), "{text} is geen getal"),
    (re.compile(r"^(?P<text>.+) is not a valid date$"), "{text} is geen geldige datum"),
    (re.compile(r"^(?P<text>.+) is not a date$"), "{text} is geen datum"),
    (re.compile(r"^(?P<text>.+) is not yes or no$"), "{text} is geen ja of nee"),
]

# Pydantic validation errors by type; ``{...}`` is filled from the error's context.
PYDANTIC: dict[str, str] = {
    "missing": "Vul dit veld in",
    "string_too_short": "Vul dit veld in",
    "string_too_long": "Hoogstens {max_length} tekens",
    "greater_than": "Moet groter zijn dan {gt}",
    "greater_than_equal": "Moet minstens {ge} zijn",
    "less_than": "Moet kleiner zijn dan {lt}",
    "less_than_equal": "Mag hoogstens {le} zijn",
    "float_parsing": "Vul een getal in",
    "float_type": "Vul een getal in",
    "int_parsing": "Vul een heel getal in",
    "int_type": "Vul een heel getal in",
    "int_from_float": "Vul een heel getal in",
    "date_parsing": "Vul een geldige datum in",
    "date_type": "Vul een geldige datum in",
    "date_from_datetime_parsing": "Vul een geldige datum in",
    "datetime_parsing": "Vul een geldige datum en tijd in",
    "datetime_type": "Vul een geldige datum en tijd in",
    "datetime_from_date_parsing": "Vul een geldige datum en tijd in",
    "timezone_aware": "Een tijdstip moet een tijdzone hebben",
    "bool_parsing": "Kies ja of nee",
    "bool_type": "Kies ja of nee",
    "literal_error": "Kies een van de opties",
    "enum": "Kies een van de opties",
    "string_pattern_mismatch": "Ongeldige waarde",
    "extra_forbidden": "Onbekend veld",
}


def translate(message: str, lang: str) -> str:
    """``message`` in ``lang``; English, or a message without a translation, stays as it is."""
    if lang != "nl":
        return message
    if message in EXACT:
        return EXACT[message]
    for pattern, template in PATTERNS:
        match = pattern.match(message)
        if match:
            return template.format(**match.groupdict())
    # Several messages joined into one ("a; b") are translated one by one.
    if "; " in message:
        return "; ".join(translate(part, lang) for part in message.split("; "))
    return message


def validation_message(error: Mapping, lang: str) -> str:
    """The message of one pydantic validation error, in ``lang``."""
    message = str(error.get("msg", "Invalid value")).removeprefix("Value error, ")
    if lang != "nl":
        return message
    kind = error.get("type", "")
    if kind == "value_error":
        return translate(message, lang)
    template = PYDANTIC.get(kind)
    if template is None:
        return translate(message, lang)
    context = {key: _plain(value) for key, value in (error.get("ctx") or {}).items()}
    try:
        return template.format(**context)
    except (KeyError, IndexError):
        return template


def _plain(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).replace(".", ",") if isinstance(value, float) else str(value)
