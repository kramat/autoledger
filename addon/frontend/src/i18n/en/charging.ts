// Texts of the charging area.

export default {
  nouns: { charge: 'Charge' },
  head: {
    exportCsv: 'Export CSV',
    addPublic: 'Add public charge',
  },
  status: {
    chargingNow: 'Charging now',
    needsPrice: 'Needs price',
    kwhEstimated: 'kWh estimated',
  },
  columns: {
    start: 'Start',
    where: 'Where',
    battery: 'Battery',
    perKwh: 'Per kWh',
    cost: 'Cost',
    status: 'Status',
  },
  fields: {
    kind: 'Type',
    energy: 'Energy (kWh)',
    start: 'Start',
    end: 'End',
    priceMode: 'Price',
    pricePerKwh: 'Price per kWh',
    sessionFee: 'Start fee',
    priceTotal: 'Total paid',
    socStart: 'Battery at start (%)',
    socEnd: 'Battery at end (%)',
    provider: 'Provider',
    providerPlaceholder: 'e.g. Fastned',
    address: 'Location',
    note: 'Note',
  },
  dialog: { add: 'Add charge', edit: 'Edit charge' },
  empty: 'No charges yet. Home charging appears here automatically once the AutoLedger Collector is set up.',
  count: { one: '{n} charge', other: '{n} charges' },
  footnote:
    'Home sessions are priced per kWh at the moment it was delivered, using your electricity price sensor. Edit a session to set your own price, a total, or mark it free.',
  efficiency: {
    title: 'Efficiency · {name}',
    uses: 'Trips use {factor} ({mode}), so a full battery costs {full} kWh of charging, losses included.',
    factor: '{value} kWh from the wall per battery %',
    learned: {
      one: 'Learned: {value}, from the last home charge that added at least 20 %.',
      other: 'Learned: {value}, the median of the last {n} home charges that added at least 20 %.',
    },
    learning: 'Learning needs 3 home charges that add at least 20 % with the battery % known; {n} so far.',
    fromCapacity: 'From the battery capacity: {value}.',
    setYourself: 'Set it yourself (kWh per %)',
    useLearned: 'Use the learned value',
  },
  toast: {
    usingLearned: 'Using the learned value',
    factorSaved: 'kWh per % saved',
  },
}
