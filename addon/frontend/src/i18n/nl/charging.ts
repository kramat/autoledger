import type en from '../en/charging'

const charging: typeof en = {
  nouns: { charge: 'Laadbeurt' },
  head: {
    exportCsv: 'CSV exporteren',
    addPublic: 'Publieke laadbeurt toevoegen',
  },
  status: {
    chargingNow: 'Laadt nu',
    needsPrice: 'Prijs ontbreekt',
    kwhEstimated: 'kWh geschat',
  },
  columns: {
    start: 'Start',
    where: 'Waar',
    battery: 'Accu',
    perKwh: 'Per kWh',
    cost: 'Kosten',
    status: 'Status',
  },
  fields: {
    kind: 'Soort',
    energy: 'Energie (kWh)',
    start: 'Start',
    end: 'Einde',
    priceMode: 'Prijs',
    pricePerKwh: 'Prijs per kWh',
    sessionFee: 'Starttarief',
    priceTotal: 'Totaal betaald',
    socStart: 'Accu bij start (%)',
    socEnd: 'Accu bij einde (%)',
    provider: 'Aanbieder',
    providerPlaceholder: 'bijv. Fastned',
    address: 'Locatie',
    note: 'Notitie',
  },
  dialog: { add: 'Laadbeurt toevoegen', edit: 'Laadbeurt bewerken' },
  empty: 'Nog geen laadbeurten. Thuisladen verschijnt hier vanzelf zodra de AutoLedger Collector is ingesteld.',
  count: { one: '{n} laadbeurt', other: '{n} laadbeurten' },
  footnote:
    'Laadsessies thuis krijgen per kWh de stroomprijs van het moment van laden, uit je stroomprijssensor. Bewerk een laadsessie om zelf een prijs of totaalbedrag in te vullen, of om hem op gratis te zetten.',
  efficiency: {
    title: 'Rendement · {name}',
    uses: 'Ritten rekenen met {factor} ({mode}), dus een volle accu kost {full} kWh laden, verliezen inbegrepen.',
    factor: '{value} kWh uit het stopcontact per procent accu',
    learned: {
      one: 'Geleerd: {value}, uit de laatste laadbeurt thuis die minstens 20 % toevoegde.',
      other: 'Geleerd: {value}, de mediaan van de laatste {n} laadbeurten thuis die minstens 20 % toevoegden.',
    },
    learning:
      'Om te leren zijn 3 laadbeurten thuis nodig die minstens 20 % toevoegen, met bekend accupercentage; tot nu toe {n}.',
    fromCapacity: 'Op basis van de accucapaciteit: {value}.',
    setYourself: 'Zelf instellen (kWh per %)',
    useLearned: 'Geleerde waarde gebruiken',
  },
  toast: {
    usingLearned: 'De geleerde waarde wordt gebruikt',
    factorSaved: 'kWh per % opgeslagen',
  },
}

export default charging
