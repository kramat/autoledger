// Texts of the trips area.

export default {
  nouns: { trip: 'Trip', record: 'Record' },
  head: {
    display: 'Display',
    list: 'List',
    map: 'Map',
    exportCsv: 'Export CSV',
    add: 'Add trip',
  },
  stats: {
    electricity: 'Electricity',
    fuel: 'Fuel',
    cost: 'Cost',
    perKm: '{amount} / km',
  },
  columns: {
    date: 'Date',
    route: 'From → to',
    cost: 'Cost',
    perKm: 'Per km',
  },
  empty: {
    noCollector:
      "Trips are recorded automatically for cars set up in the AutoLedger Collector. A manual vehicle's distance comes from its odometer readings.",
    none: 'No trips in this period.',
  },
  details: 'Details',
  footnote:
    '~ before a time: the car reported only after the trip, so the start is when it was last seen parked. Fuel is smoothed for gauge noise, so it can still shift a little with the next reports; ✓ fuel: corrected with the litres refuelled between two full tanks.',
  fields: {
    start: 'Start',
    end: 'End',
    from: 'From',
    to: 'To',
    kind: 'Kind',
    distance: 'Distance (km)',
    batteryStart: 'Battery at start (%)',
    batteryEnd: 'Battery at end (%)',
    energy: 'Electricity (kWh)',
    energyHint: 'Leave empty to derive it from the battery % used.',
    fuel: 'Fuel (L)',
    note: 'Note',
  },
  dialog: { add: 'Add trip', edit: 'Edit trip' },
  idle: {
    title: 'Climate & standby',
    intro: 'Energy used while parked (pre-heating, standby). It is part of the energy cost, but not of the consumption per km.',
    columns: { parked: 'Parked', where: 'Where', battery: 'Battery', cost: 'Cost' },
    records: { one: '{n} record', other: '{n} records' },
    fields: {
      where: 'Where',
      batteryUsed: 'Battery used (%)',
    },
    editTitle: 'Edit climate & standby',
  },
  detail: {
    ariaLabel: 'Trip details',
    startEstimated: 'start estimated',
    distanceSources: { trip_meter: 'trip meter', odometer: 'odometer', manual: 'entered by hand' },
    facts: {
      odometer: 'Odometer',
      battery: 'Battery',
      batteryValue: '{start} → {end} % (used {used} %)',
      chargedBetween: 'Charged in between',
      tank: 'Tank',
    },
    explain: {
      title: 'How the cost was calculated',
      electricity: 'Electricity',
      fuel: 'Fuel',
      trip: 'Trip',
      fuelReconciled: '(gauge {measured} L, corrected at the full tank)',
      fuelSmoothed: '(gauge {measured} L, smoothed for gauge noise; provisional until the next full tank)',
      fuelProvisional: '(provisional until the next full tank)',
      perKm: '{amount} / km',
      pricesNote:
        'Prices are the average of what is in the battery and in the tank: your charges and refuels, mixed in proportion.',
    },
    split: {
      stopAfter: 'Stop after (km)',
      stopTime: 'Stop time',
      stopPlace: 'Stop place',
      stopPlacePlaceholder: 'e.g. Albert Heijn',
      submit: 'Split trip',
    },
    actions: {
      mergePrevious: 'Merge with previous',
      mergeNext: 'Merge with next',
      split: 'Split…',
    },
    toast: { merged: 'Trips merged', split: 'Trip split' },
  },
  map: {
    ariaLabel: 'Map of trip start and end points',
    unknownPlace: 'unknown place',
    start: 'start',
    end: 'end',
    straightLines: 'lines are straight, the route is not recorded',
  },
}
