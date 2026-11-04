// Gedeelde teksten. Woordenlijst, zodat alle pagina's dezelfde woorden gebruiken (je-vorm):
//
//   trip → rit · round trip → rondrit · one way → enkele reis · refuel → tankbeurt
//   odometer → kilometerstand · trip meter → dagteller · charge session → laadsessie
//   home charger → thuislader · public charging → publiek laden · charge → laden / laadbeurt
//   fuel (tab) → Tanken · fuel (cost) → brandstof · electricity → stroom
//   consumption → verbruik · climate & standby → klimaat & stand-by · battery (car) → accu
//   maintenance → onderhoud · maintenance entry → onderhoudsbeurt · schedule → schema
//   due soon → binnenkort · overdue → te laat · costs / expense → kosten
//   recurring → terugkerend · depreciation → afschrijving · receipt → bon · invoice → factuur
//   review (inbox) → controleren · vehicle → voertuig · report → rapport · backup → back-up
//   restore → terugzetten · import / export → importeren / exporteren · period → periode
import type en from '../en/common'

const common: typeof en = {
  app: {
    filters: { vehicle: 'Voertuig', period: 'Periode', allVehicles: 'Alle voertuigen', from: 'Van', to: 'Tot en met' },
    openFromSidebar: 'Open AutoLedger via de zijbalk van Home Assistant.',
    cannotReach: 'De AutoLedger-API is niet bereikbaar: {error}',
    sections: 'Onderdelen',
  },
  nav: {
    overview: 'Overzicht',
    trips: 'Ritten',
    fuel: 'Tanken',
    charging: 'Laden',
    maintenance: 'Onderhoud',
    costs: 'Kosten',
    reports: 'Rapporten',
    review: 'Controleren',
    vehicles: 'Voertuigen',
    settings: 'Instellingen',
  },
  presets: {
    this_month: 'Deze maand',
    last_month: 'Vorige maand',
    this_year: 'Dit jaar',
    last_year: 'Vorig jaar',
    last_12m: 'Afgelopen 12 maanden',
    all: 'Alles',
    custom: 'Zelf kiezen…',
  },
  actions: {
    add: 'Toevoegen',
    save: 'Opslaan',
    cancel: 'Annuleren',
    edit: 'Bewerken',
    delete: 'Verwijderen',
    undo: 'Ongedaan maken',
    close: 'Sluiten',
    actions: 'Acties',
    loading: 'Even geduld…',
  },
  toast: {
    added: '{noun} toegevoegd',
    saved: '{noun} opgeslagen',
    deleted: '{noun} verwijderd',
  },
  attachments: {
    title: 'Bon of factuur',
    add: 'Foto of pdf toevoegen',
    uploading: 'Uploaden…',
    remove: 'Weghalen',
    removed: '{name} weggehaald',
    pending: 'wordt toegevoegd bij opslaan',
  },
  labels: {
    vehicleTypes: { ICE: 'Brandstof (ICE)', PHEV: 'Plug-in hybride (PHEV)', BEV: 'Elektrisch (BEV)' },
    fuelTypes: { petrol: 'Benzine', diesel: 'Diesel', lpg: 'Lpg', none: 'Geen' },
    maintenanceCategories: {
      service: 'Onderhoudsbeurt',
      inspection: 'APK',
      tyres: 'Banden',
      repair: 'Reparatie',
      battery: 'Accu',
      cleaning: 'Schoonmaak',
      other: 'Overig',
    },
    expenseCategories: {
      insurance: 'Verzekering',
      road_tax: 'Wegenbelasting (MRB)',
      parking: 'Parkeren',
      tolls: 'Tol',
      car_wash: 'Wasstraat',
      fine: 'Boete',
      accessories: 'Accessoires',
      lease: 'Lease',
      subscription: 'Abonnement',
      other: 'Overig',
    },
    recurrences: { once: 'Eenmalig', monthly: 'Elke maand', quarterly: 'Elk kwartaal', yearly: 'Elk jaar' },
    chargeKinds: { home: 'Thuis', public: 'Publiek', manual: 'Overig' },
    priceModes: {
      per_kwh: 'Prijs per kWh',
      total: 'Totaalbedrag',
      free: 'Gratis',
      samples: 'Actuele stroomprijs (thuislader)',
    },
    tripKinds: { one_way: 'Enkele reis', round_trip: 'Rondrit' },
    factorModes: { manual: 'door jou ingesteld', learned: 'geleerd van thuisladen', default: 'op basis van accucapaciteit' },
    dueStatuses: { ok: '✓ Op schema', soon: '⚠ Binnenkort', overdue: '⛔ Te laat', unknown: '? Nog onbekend' },
    importResources: {
      refuels: 'Tankbeurten',
      maintenance: 'Onderhoud',
      odometerReadings: 'Kilometerstanden',
      expenses: 'Overige kosten (eenmalig)',
    },
    importFields: {
      ts: 'Datum (en tijd)',
      date: 'Datum',
      litres: 'Liters',
      price_per_l: 'Prijs per liter',
      total: 'Totaal betaald',
      odometer_km: 'Kilometerstand (km)',
      full_tank: 'Volle tank',
      station: 'Tankstation',
      note: 'Notitie',
      category: 'Categorie',
      description: 'Omschrijving',
      garage: 'Garage',
      cost: 'Kosten',
      amount: 'Bedrag',
    },
    reviewReasons: {
      refuel_price: 'Tankbeurt gezien: controleer de liters en vul in wat je betaalde',
      public_charge_price: 'Geladen buiten de deur: vul in wat je betaalde',
      possible_engine_charge: 'Accu ging omhoog tijdens het rijden: publiek geladen, of door de motor?',
      charge_without_vehicle: 'Thuis geladen zonder voertuig: welke auto was het?',
      rejected_event: 'De Collector stuurde gegevens die niet verwerkt konden worden',
    },
    languages: { auto: 'Automatisch (taal van de browser)', en: 'English', nl: 'Nederlands' },
  },
}

export default common
