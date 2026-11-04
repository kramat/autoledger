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
    'Terugkerende kosten worden verdeeld over de maanden waar ze voor gelden: een verzekering van 600 per jaar telt als 50 per maand, tot en met de huidige maand.',
  dialogs: { add: 'Kosten toevoegen', edit: 'Kosten bewerken' },
}

export default costs
