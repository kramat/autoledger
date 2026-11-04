// Texts of the costs area.

export default {
  noun: 'Expense',
  title: 'Other costs',
  actions: { exportCsv: 'Export CSV', add: 'Add cost' },
  repeatsUntil: '{recurrence} until {date}',
  columns: {
    date: 'Date',
    vehicle: 'Vehicle',
    category: 'Category',
    amount: 'Amount',
    repeats: 'Repeats',
    note: 'Note',
    receipt: 'Receipt',
  },
  fields: {
    category: 'Category',
    amount: 'Amount',
    amountHint: 'For a recurring cost: the amount per period, e.g. per year',
    recurrence: 'Repeats',
    date: 'Date (start date when recurring)',
    endDate: 'Ends on',
    endDateHint: 'Leave empty if it is still running',
    note: 'Note',
  },
  empty: 'No costs yet. Add insurance, road tax, parking, tolls and other costs here.',
  spreadNote:
    'Recurring costs are spread over the months they cover: a yearly insurance of 600 counts as 50 per month, up to the current month.',
  dialogs: { add: 'Add cost', edit: 'Edit cost' },
}
