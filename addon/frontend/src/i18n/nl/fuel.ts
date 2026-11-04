import type en from '../en/fuel'

const fuel: typeof en = {
  nouns: { refuel: 'Tankbeurt', reading: 'Kilometerstand' },
  tabs: { show: 'Tonen', refuels: 'Tankbeurten', readings: 'Kilometerstanden' },
  actions: { exportCsv: 'CSV exporteren', addRefuel: 'Tankbeurt toevoegen', addReading: 'Stand toevoegen' },
  columns: {
    date: 'Datum',
    vehicle: 'Voertuig',
    odometer: 'Kilometerstand',
    litres: 'Liters',
    pricePerL: 'Prijs / L',
    total: 'Totaal',
    tank: 'Tank',
    full: 'Vol',
    partial: 'Deels',
    consumption: 'L/100 km',
    station: 'Tankstation',
    receipt: 'Bon',
    note: 'Notitie',
  },
  fields: {
    ts: 'Datum en tijd',
    odometer: 'Kilometerstand (km)',
    odometerHint: 'Nodig voor L/100 km',
    fullTank: 'Tank helemaal volgetankt',
    litres: 'Liters',
    total: 'Totaal betaald',
    pricePerL: 'Prijs per liter',
    pricePerLHint: 'Vul twee van de drie in: liters, totaal of prijs per liter. De derde wordt berekend.',
    station: 'Tankstation',
    note: 'Notitie',
  },
  refuels: {
    empty: 'Nog geen tankbeurten.',
    count: { one: '{n} tankbeurt', other: '{n} tankbeurten' },
    consumptionNote: 'L/100 km wordt berekend van volle tank tot volle tank, inclusief gedeeltelijke tankbeurten daartussen.',
  },
  readings: {
    empty: 'Nog geen kilometerstanden. Tankbeurten en onderhoud met een kilometerstand tellen ook mee.',
  },
  dialogs: {
    addRefuel: 'Tankbeurt toevoegen',
    editRefuel: 'Tankbeurt bewerken',
    addReading: 'Kilometerstand toevoegen',
    editReading: 'Kilometerstand bewerken',
  },
}

export default fuel
