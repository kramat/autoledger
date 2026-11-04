import type en from '../en/vehicles'

const vehicles: typeof en = {
  noun: 'Voertuig',
  title: 'Voertuigen',
  add: 'Voertuig toevoegen',
  empty: 'Nog geen voertuigen.',
  archivedNote: 'Gearchiveerde voertuigen verdwijnen uit de voertuigkeuze, maar blijven in de rapporten.',
  archivedCount: '{n} gearchiveerd.',
  archive: 'Archiveren',
  unarchive: 'Uit archief halen',
  toast: { archived: '{name} gearchiveerd', restored: '{name} uit archief gehaald' },
  columns: {
    name: 'Naam',
    archivedName: '{name} (gearchiveerd)',
    type: 'Type',
    fuel: 'Brandstof',
    plate: 'Kenteken',
    capacity: 'Tank / accu',
    start: 'Bijgehouden vanaf',
    startValue: '{odometer} op {date}',
  },
  fields: {
    name: 'Naam',
    namePlaceholder: 'bijv. VW Up',
    make: 'Merk',
    model: 'Model',
    year: 'Bouwjaar',
    plate: 'Kenteken',
    type: 'Type',
    fuel: 'Brandstof',
    tank: 'Tankinhoud (L)',
    battery: 'Bruikbare accucapaciteit (kWh)',
    kwhPerPct: 'kWh uit het stopcontact per procent accu',
    kwhPerPctHint:
      'Stroom uit het stopcontact voor 1 % accu, inclusief laadverlies. 16,5 kWh voor een volle accu → 0,165. Leeg: bruikbare capaciteit / 90 %.',
    startDate: 'Bijhouden vanaf',
    startDateHint: 'De vroegste datum waarvan je gegevens hebt',
    startOdometer: 'Kilometerstand op die datum (km)',
    purchaseDate: 'Aankoopdatum',
    purchasePrice: 'Aankoopprijs',
    resaleDate: 'Verwachte verkoopdatum',
    resaleEstimate: 'Verwachte verkoopwaarde',
    depreciation: 'Afschrijving meetellen in de kosten',
    depreciationHint:
      '(Aankoop − verkoop) gelijk verdeeld over de maanden daartussen, geteld vanaf de startdatum tot vandaag.',
    color: 'Kleur in grafieken',
    note: 'Notitie',
  },
  dialogs: { add: 'Voertuig toevoegen', edit: 'Voertuig bewerken' },
}

export default vehicles
