import type en from '../en/settings'

const settings: typeof en = {
  general: {
    title: 'Algemeen',
    language: 'Taal',
  },
  prices: {
    title: 'Prijzen en valuta',
    hint: 'Standaardprijzen voor als een prijs niet bekend is, ook voor de Collector.',
    currency: 'Valuta (ISO-code)',
    electricity: 'Stroom, standaardprijs per kWh',
    publicCharge: 'Publiek laden, standaardprijs per kWh',
    petrol: 'Benzine, standaardprijs per liter',
    diesel: 'Diesel, standaardprijs per liter',
    lpg: 'Lpg, standaardprijs per liter',
  },
  toast: {
    saved: 'Instellingen opgeslagen',
    notSaved: 'Niet opgeslagen: {error}',
  },
  export: {
    title: 'Exporteren',
    hint: 'Alle gegevens in één Excel-werkmap (een tabblad per soort), of een CSV-bestand per soort.',
    workbook: 'Alle gegevens (XLSX)',
    resources: {
      refuels: 'Tankbeurten',
      odometerReadings: 'Kilometerstanden',
      charges: 'Laadsessies',
      idleRecords: 'Klimaat & stand-by',
      maintenanceSchedules: 'Onderhoudsschema’s',
      expenses: 'Overige kosten',
    },
  },
  import: {
    title: 'Importeren',
    hint: 'Tankbeurten, onderhoud, kilometerstanden of overige kosten uit een CSV-bestand, bijvoorbeeld je geschiedenis uit een spreadsheet. Je controleert de kolommen in een voorbeeld voordat er iets wordt opgeslagen.',
    button: 'CSV importeren…',
    imported: { one: '{n} regel geïmporteerd', other: '{n} regels geïmporteerd' },
  },
  backup: {
    title: 'Back-up',
    hint: 'Een volledige JSON-back-up van alles in AutoLedger, om over te zetten naar een andere installatie. Back-ups van Home Assistant bevatten ook de database en de bonnen van de add-on. Het API-token staat niet in het bestand.',
    withFiles: 'Foto’s van bonnen en facturen meenemen',
    withFilesHint: 'Het bestand wordt dan groter. Zonder deze bestanden houdt een teruggezette back-up de lijst met bijlagen, maar niet de bestanden zelf.',
    download: 'Back-up downloaden',
  },
  restore: {
    title: 'Terugzetten',
    file: 'Back-upbestand',
    mode: 'Hoe',
    modes: {
      empty: 'In deze add-on, zolang die nog leeg is',
      merge: 'Aanvullen wat ontbreekt, houden wat er al is',
    },
    copyFirst: 'De huidige database wordt eerst gekopieerd naar /data/backups.',
    button: 'Terugzetten',
    done: 'Back-up teruggezet',
    notJson: 'Dit bestand is geen JSON-back-up.',
    restored: { one: '{n} item teruggezet.', other: '{n} items teruggezet.' },
    skipped: { one: '{n} was er al.', other: '{n} waren er al.' },
    files: { one: 'Ook {n} bon teruggezet.', other: 'Ook {n} bonnen teruggezet.' },
  },
  token: {
    title: 'API-token',
    hint: 'De AutoLedger Collector-integratie en je eigen scripts gebruiken dit token. Houd het geheim.',
    show: 'Tonen',
    hide: 'Verbergen',
    copy: 'Kopiëren',
    create: 'Nieuw token maken',
    confirm: 'Klik nogmaals om het token te vervangen',
    created: 'Nieuw token gemaakt. Vervang het overal waar je het oude gebruikte.',
    copied: 'Token gekopieerd',
  },
  collector: {
    title: 'Collector',
    lastData: 'Laatste gegevens van de AutoLedger Collector: {time}.',
    noData: 'De AutoLedger Collector heeft nog geen gegevens gestuurd. Installeer hem via HACS en voeg de integratie toe.',
  },
  about: '{name} {version} · API v{apiVersion} · Tijdzone {timezone}',
}

export default settings
