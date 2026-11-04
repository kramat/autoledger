import type en from '../en/review'

const review: typeof en = {
  empty: 'Niets te controleren. Alles is bevestigd.',
  toast: {
    removed: 'Verwijderd',
    dismissed: 'Genegeerd',
    saved: 'Opgeslagen',
  },
  refuel: {
    when: '{time}.',
    whenAt: '{time} bij {station}.',
    details: 'De tank is ongeveer {litres} L voller geworden. Voorgestelde prijs {price}/L ({total}).',
    litres: 'Liters (van de bon)',
    total: 'Totaal betaald',
    totalPlaceholder: 'Van de bon',
    keepSuggestion: 'Voorstel houden',
    notRefuel: 'Geen tankbeurt',
  },
  charge: {
    details: 'Tussen {start} en {end} ging de accu van {socStart} % naar {socEnd} %, ongeveer {energy} kWh.',
    detailsNear: 'Tussen {start} en {end} ging de accu van {socStart} % naar {socEnd} %, ongeveer {energy} kWh, in de buurt van {address}.',
    energy: 'Energie (kWh)',
    pricePerKwh: 'Prijs per kWh',
    total: 'Of het totaal betaald',
    totalPlaceholder: 'Gaat voor de prijs per kWh',
    free: 'Het was gratis',
    byEngine: 'Geladen door de motor',
    notCharge: 'Geen laadbeurt',
  },
  homeCharge: {
    details: '{time}: {energy} kWh voor {cost} op {charger}.',
    homeCharger: 'de thuislader',
    vehicle: 'Voertuig',
    remove: 'Laadsessie verwijderen',
  },
  other: {
    noDetails: 'Geen details',
    dismiss: 'Negeren',
  },
}

export default review
