"""Write tables to an .xlsx workbook (one sheet per table)."""

import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_INVALID_TITLE = str.maketrans({c: "-" for c in "[]:*?/\\"})


@dataclass
class Sheet:
    title: str
    columns: Sequence[str]
    rows: Iterable[Sequence]


def _value(value, tz: ZoneInfo):
    """Excel has no time zones: datetimes are written in local time."""
    if isinstance(value, datetime):
        return value.astimezone(tz).replace(tzinfo=None)
    if isinstance(value, (list, dict)):
        return str(value) if value else None
    return value


def workbook(sheets: Sequence[Sheet], tz: ZoneInfo) -> bytes:
    book = Workbook(write_only=True)
    bold = Font(bold=True)
    for sheet in sheets:
        ws = book.create_sheet(sheet.title.translate(_INVALID_TITLE)[:31])
        widths = [len(c) for c in sheet.columns]
        header = []
        for name in sheet.columns:
            cell = WriteOnlyCell(ws, value=name)
            cell.font = bold
            header.append(cell)
        rows = []
        for row in sheet.rows:
            values = [_value(v, tz) for v in row]
            for i, v in enumerate(values):
                widths[i] = max(widths[i], 19 if isinstance(v, datetime) else 10 if isinstance(v, date)
                                else len(str(v)) if v is not None else 0)
            rows.append(values)
        # Column widths must be set before the first row in write-only mode.
        for i, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 8), 50)
        ws.freeze_panes = "A2"
        ws.append(header)
        for values in rows:
            cells = []
            for v in values:
                cell = WriteOnlyCell(ws, value=v)
                if isinstance(v, datetime):
                    cell.number_format = "yyyy-mm-dd hh:mm"
                elif isinstance(v, date):
                    cell.number_format = "yyyy-mm-dd"
                cells.append(cell)
            ws.append(cells)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
