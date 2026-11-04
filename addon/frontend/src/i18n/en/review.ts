// Texts of the review area.

export default {
  empty: 'Nothing to review. Everything is confirmed.',
  toast: {
    removed: 'Removed',
    dismissed: 'Dismissed',
    saved: 'Saved',
  },
  refuel: {
    when: '{time}.',
    whenAt: '{time} at {station}.',
    details: 'The fuel level rose by about {litres} L. Suggested price {price}/L ({total}).',
    litres: 'Litres (from the receipt)',
    total: 'Total paid',
    totalPlaceholder: 'From the receipt',
    keepSuggestion: 'Keep suggestion',
    notRefuel: 'Not a refuel',
  },
  charge: {
    details: 'Between {start} and {end} the battery went from {socStart} % to {socEnd} %, about {energy} kWh.',
    detailsNear: 'Between {start} and {end} the battery went from {socStart} % to {socEnd} %, about {energy} kWh near {address}.',
    energy: 'Energy (kWh)',
    pricePerKwh: 'Price per kWh',
    total: 'Or the total paid',
    totalPlaceholder: 'Overrides the price per kWh',
    free: 'It was free',
    byEngine: 'Charged by the engine',
    notCharge: 'Not a charge',
  },
  homeCharge: {
    details: '{time}: {energy} kWh for {cost} on {charger}.',
    homeCharger: 'the home charger',
    vehicle: 'Vehicle',
    remove: 'Remove session',
  },
  other: {
    noDetails: 'No details',
    dismiss: 'Dismiss',
  },
}
