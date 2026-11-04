// Texts of the fuel area.

export default {
  nouns: { refuel: 'Refuel', reading: 'Odometer reading' },
  tabs: { show: 'Show', refuels: 'Refuels', readings: 'Odometer readings' },
  actions: { exportCsv: 'Export CSV', addRefuel: 'Add refuel', addReading: 'Add reading' },
  columns: {
    date: 'Date',
    vehicle: 'Vehicle',
    odometer: 'Odometer',
    litres: 'Litres',
    pricePerL: 'Price / L',
    total: 'Total',
    tank: 'Tank',
    full: 'Full',
    partial: 'Partial',
    consumption: 'L/100 km',
    station: 'Station',
    receipt: 'Receipt',
    note: 'Note',
  },
  fields: {
    ts: 'Date and time',
    odometer: 'Odometer (km)',
    odometerHint: 'Needed for L/100 km',
    fullTank: 'Filled the tank completely',
    litres: 'Litres',
    total: 'Total paid',
    pricePerL: 'Price per litre',
    pricePerLHint: 'Fill in two of litres, total and price per litre. The third is calculated.',
    station: 'Station',
    note: 'Note',
  },
  refuels: {
    empty: 'No refuels yet.',
    count: { one: '{n} refuel', other: '{n} refuels' },
    consumptionNote: 'L/100 km is calculated from one full tank to the next, including partial refuels in between.',
  },
  readings: {
    empty: 'No odometer readings yet. Refuels and maintenance with an odometer value count too.',
  },
  dialogs: {
    addRefuel: 'Add refuel',
    editRefuel: 'Edit refuel',
    addReading: 'Add odometer reading',
    editReading: 'Edit odometer reading',
  },
}
