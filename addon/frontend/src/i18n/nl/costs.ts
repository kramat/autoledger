import type en from '../en/costs'

const costs: typeof en = {
  noun: 'Kosten',
  title: 'Overige kosten',
  actions: { exportCsv: 'CSV exporteren', add: 'Kosten toevoegen' },
  repeatsUntil: '{recurrence} tot en met {date}',
  columns: {
    date: 'Datum',
    vehicle: 'Voertuig',
    category: 'Categorie',
    amount: 'Bedrag',
    repeats: 'Herhaling',
    note: 'Notitie',
    receipt: 'Bon',
  },
  fields: {
    split: 'Voor',
    splitVehicles: 'Gedeeld door',
    splitVehiclesHint: 'Het bedrag is de hele rekening; elk voertuig telt zijn deel',
    category: 'Categorie',
    amount: 'Bedrag',
    amountHint: 'Bij terugkerende kosten: het bedrag per periode, bijvoorbeeld per jaar',
    recurrence: 'Herhaling',
    date: 'Datum (startdatum bij terugkerende kosten)',
    endDate: 'Loopt tot en met',
    endDateHint: 'Laat leeg als het nog doorloopt',
    note: 'Notitie',
  },
  empty: 'Nog geen kosten. Voeg hier verzekering, wegenbelasting, parkeren, tol en andere kosten toe.',
  spreadNote:
    'Terugkerende kosten worden verdeeld over de maanden waar ze voor gelden: een verzekering van 600 per jaar telt als 50 per maand, tot en met de huidige maand. ' +
    'Gedeelde kosten worden elke maand verdeeld over de voertuigen die toen in gebruik waren: gelijk, naar de km die elk die maand reed, of met vaste percentages.',
  dialogs: { add: 'Kosten toevoegen', edit: 'Kosten bewerken' },
}

export default costs
