import type en from '../en/overview'

const overview: typeof en = {
  welcome: {
    title: 'Welkom bij AutoLedger',
    text: 'Voeg je eerste voertuig toe en houd tankbeurten, onderhoud en kosten bij.',
    addVehicle: 'Voertuig toevoegen',
  },
  reviewNotice: {
    one: '{n} punt wacht op je bij Controleren.',
    other: '{n} punten wachten op je bij Controleren.',
  },
  stats: {
    distance: 'Afstand',
    odometer: 'Kilometerstand {km}',
    totalCost: 'Totale kosten',
    perKm: '{amount} / km',
    fuel: 'Brandstof',
    electricity: 'Stroom',
    kwhUsed: '{kwh} kWh verbruikt',
    charges: { one: '{n} laadbeurt', other: '{n} laadbeurten' },
    maintenance: 'Onderhoud',
    entries: { one: '{n} onderhoudsbeurt', other: '{n} onderhoudsbeurten' },
    otherCosts: 'Overige kosten',
    otherHint: 'Verzekering, belasting, parkeren…',
    depreciation: 'Afschrijving',
    depreciationHint: 'Waardeverlies, verdeeld per maand',
    energy: 'Energie',
  },
  rolling: {
    distance: 'Afgelopen 12 maanden: {km}',
    totalPerKm: '{amount} / km totaal',
    energyPerKm: '{amount} / km energie',
    electricShare: '{pct}% van de km elektrisch (schatting)',
  },
  lastTrip: {
    label: 'Laatste rit {date}:',
    detail: '{distance} km voor {cost}',
    roundTrip: 'rondrit vanaf {place}',
  },
  idle: {
    electric: 'Klimaat & stand-by: {kwh} kWh voor {cost} (telt mee in de energiekosten, niet in de € per km)',
    withFuel: 'Klimaat & stand-by: {kwh} kWh en {litres} L voor {cost} (telt mee in de energiekosten, niet in de € per km)',
  },
  charging: {
    now: 'Nu aan het laden',
    since: 'sinds {date}: {kwh} kWh, {cost}',
    last: 'Laatste laadbeurt {date}: {kwh} kWh voor {cost}',
  },
  lastRefuel: 'Laatste tankbeurt {date}: {litres} L voor {cost}',
  due: {
    due: 'op {date}',
    wasDue: 'was op {date} nodig',
    kmLeft: 'nog {km}',
    kmOver: '{km} te laat',
  },
  distanceKnownUntil:
    'De afstand is bekend tot en met {date}. Voeg een kilometerstand toe, of een tankbeurt met kilometerstand, voor de km daarna.',
  odometerIgnored: {
    one: '{n} kilometerstand is lager dan een eerdere en is genegeerd. Kijk het na op de pagina Tanken.',
    other: '{n} kilometerstanden zijn lager dan een eerdere en zijn genegeerd. Kijk ze na op de pagina Tanken.',
  },
  monthly: {
    title: 'Afgelopen 12 maanden',
    titleAll: 'Afgelopen 12 maanden · alle voertuigen',
    display: 'Weergave',
    chart: 'Grafiek',
    table: 'Tabel',
    costPerMonth: 'Kosten per maand',
    costChartLabel: 'Gestapeld staafdiagram van de kosten per maand, per categorie',
    distancePerMonth: 'Afstand per maand',
    distanceChartLabel: 'Staafdiagram van de gereden km per maand',
    tooltipTotal: 'Totaal: {amount}',
    note:
      "Bij auto's met vastgelegde ritten tellen brandstof en stroom mee wanneer je ze verbruikt. Bij andere auto's telt " +
      'brandstof in de maand waarin je tankte, dus losse maanden kunnen schommelen; de 12-maandcijfers hierboven vlakken dat af.',
  },
  categories: {
    fuel: 'Brandstof',
    electricity: 'Stroom',
    maintenance: 'Onderhoud',
    other: 'Overig',
    otherDepreciation: 'Overig + afschrijving',
  },
  table: {
    month: 'Maand',
    km: 'km',
    fuel: 'Brandstof',
    electricity: 'Stroom',
    maintenance: 'Onderhoud',
    other: 'Overig',
    depreciation: 'Afschrijving',
    total: 'Totaal',
    perKm: 'Per km',
  },
}

export default overview
