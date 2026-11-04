// Texts of the importer area.

export default {
  title: 'Import CSV',
  intro: 'From a spreadsheet or another app. Nothing is saved until you click Import; rows that are already in AutoLedger are skipped.',
  fields: {
    resource: 'What is in the file',
    vehicle: 'Vehicle',
    file: 'CSV file',
  },
  columns: 'Columns',
  notInFile: '— not in the file —',
  decimal: {
    label: 'Decimal separator',
    comma: 'Comma (12,50)',
    point: 'Point (12.50)',
  },
  dates: {
    label: 'Dates',
    dmy: 'Day first (31-12-2025)',
    mdy: 'Month first (12/31/2025)',
    ymd: 'Year first (2025-12-31)',
  },
  summary: {
    rows: { one: '{n} row', other: '{n} rows' },
    toImport: '{n} to import',
    duplicates: '{n} already there',
    errors: '{n} with errors',
    firstShown: '(first {n} shown)',
  },
  table: {
    line: 'Line',
    status: 'Status',
    ok: '✓ ok',
    duplicate: '= already there',
  },
  yes: 'yes',
  no: 'no',
  noVehicle: 'Add a vehicle first.',
  import: 'Import',
  importRows: { one: 'Import {n} row', other: 'Import {n} rows' },
}
