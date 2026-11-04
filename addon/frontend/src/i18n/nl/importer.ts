import type en from '../en/importer'

const importer: typeof en = {
  title: 'CSV importeren',
  intro: 'Uit een spreadsheet of een andere app. Er wordt pas iets opgeslagen als je op Importeren klikt; regels die al in AutoLedger staan, worden overgeslagen.',
  fields: {
    resource: 'Wat staat er in het bestand',
    vehicle: 'Voertuig',
    file: 'CSV-bestand',
  },
  columns: 'Kolommen',
  notInFile: '— niet in het bestand —',
  decimal: {
    label: 'Decimaalteken',
    comma: 'Komma (12,50)',
    point: 'Punt (12.50)',
  },
  dates: {
    label: 'Datums',
    dmy: 'Dag eerst (31-12-2025)',
    mdy: 'Maand eerst (12/31/2025)',
    ymd: 'Jaar eerst (2025-12-31)',
  },
  summary: {
    rows: { one: '{n} regel', other: '{n} regels' },
    toImport: '{n} te importeren',
    duplicates: '{n} al aanwezig',
    errors: '{n} met fouten',
    firstShown: '(eerste {n} getoond)',
  },
  table: {
    line: 'Regel',
    status: 'Status',
    ok: '✓ ok',
    duplicate: '= al aanwezig',
  },
  yes: 'ja',
  no: 'nee',
  noVehicle: 'Voeg eerst een voertuig toe.',
  import: 'Importeren',
  importRows: { one: '{n} regel importeren', other: '{n} regels importeren' },
}

export default importer
