import type en from '../en/trips'

const trips: typeof en = {
  nouns: { trip: 'Rit', record: 'Registratie' },
  head: {
    display: 'Weergave',
    list: 'Lijst',
    map: 'Kaart',
    exportCsv: 'CSV exporteren',
    add: 'Rit toevoegen',
  },
  stats: {
    electricity: 'Stroom',
    fuel: 'Brandstof',
    cost: 'Kosten',
    perKm: '{amount} / km',
  },
  columns: {
    date: 'Datum',
    route: 'Van → naar',
    cost: 'Kosten',
    perKm: 'Per km',
  },
  empty: {
    noCollector:
      'Ritten worden automatisch vastgelegd voor auto’s die in de AutoLedger Collector zijn ingesteld. Bij een handmatig voertuig komt de afstand uit de kilometerstanden.',
    none: 'Geen ritten in deze periode.',
  },
  details: 'Details',
  footnote:
    '~ voor een tijd: de auto meldde zich pas na de rit, dus de start is het moment dat hij voor het laatst geparkeerd stond. Brandstof wordt afgevlakt tegen ruis van de brandstofmeter en kan bij volgende meldingen nog iets verschuiven; ✓ bij brandstof: gecorrigeerd met de getankte liters tussen twee volle tanks.',
  fields: {
    start: 'Start',
    end: 'Einde',
    from: 'Van',
    to: 'Naar',
    kind: 'Soort',
    distance: 'Afstand (km)',
    batteryStart: 'Accu bij start (%)',
    batteryEnd: 'Accu bij einde (%)',
    energy: 'Stroom (kWh)',
    energyHint: 'Laat leeg om het te berekenen uit het verbruikte accupercentage.',
    fuel: 'Brandstof (L)',
    note: 'Notitie',
  },
  dialog: { add: 'Rit toevoegen', edit: 'Rit bewerken' },
  idle: {
    title: 'Klimaat & stand-by',
    intro:
      'Energie die verbruikt is terwijl de auto geparkeerd stond (voorverwarmen, stand-by). Dit telt mee in de energiekosten, maar niet in het verbruik per km.',
    columns: { parked: 'Geparkeerd', where: 'Waar', battery: 'Accu', cost: 'Kosten' },
    records: { one: '{n} registratie', other: '{n} registraties' },
    fields: {
      where: 'Waar',
      batteryUsed: 'Accu verbruikt (%)',
    },
    editTitle: 'Klimaat & stand-by bewerken',
  },
  detail: {
    ariaLabel: 'Ritdetails',
    startEstimated: 'start geschat',
    distanceSources: { trip_meter: 'dagteller', odometer: 'kilometerstand', manual: 'zelf ingevuld' },
    facts: {
      odometer: 'Kilometerstand',
      battery: 'Accu',
      batteryValue: '{start} → {end} % ({used} % verbruikt)',
      chargedBetween: 'Tussendoor geladen',
      tank: 'Tank',
    },
    explain: {
      title: 'Zo zijn de kosten berekend',
      electricity: 'Stroom',
      fuel: 'Brandstof',
      trip: 'Rit',
      fuelReconciled: '(meter {measured} L, gecorrigeerd bij de volle tank)',
      fuelSmoothed: '(meter {measured} L, afgevlakt tegen meterruis; voorlopig tot de volgende volle tank)',
      fuelProvisional: '(voorlopig tot de volgende volle tank)',
      perKm: '{amount} / km',
      pricesNote:
        'De prijzen zijn het gemiddelde van wat er in de accu en de tank zit: je laadbeurten en tankbeurten, naar verhouding gemengd.',
    },
    split: {
      stopAfter: 'Stop na (km)',
      stopTime: 'Tijd van de stop',
      stopPlace: 'Plaats van de stop',
      stopPlacePlaceholder: 'bijv. Albert Heijn',
      submit: 'Rit splitsen',
    },
    actions: {
      mergePrevious: 'Samenvoegen met vorige',
      mergeNext: 'Samenvoegen met volgende',
      split: 'Splitsen…',
    },
    toast: { merged: 'Ritten samengevoegd', split: 'Rit gesplitst' },
  },
  map: {
    ariaLabel: 'Kaart met begin- en eindpunten van ritten',
    unknownPlace: 'onbekende plek',
    start: 'start',
    end: 'einde',
    straightLines: 'de lijnen zijn recht, de route wordt niet vastgelegd',
  },
}

export default trips
