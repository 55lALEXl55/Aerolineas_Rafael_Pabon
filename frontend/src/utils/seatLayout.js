// Layouts de asientos por modelo de avión
// Cada asiento: { row, col, label, class: 'FIRST'|'ECONOMY', seatNum }

export const AIRCRAFT_SPECS = {
  'A380-800': {
    engines: 4, length: '72.7m', wingspan: '79.75m',
    range: '15,200 km', cruiseSpeed: '903 km/h',
    seatsFirst: 10, seatsEconomy: 439, total: 449,
    firstRows: [1, 2], economyStartRow: 3,
    cols: { FIRST: ['A','B','D','E','F','G','H','J'], ECONOMY: ['A','B','C','D','E','F','G','H','J','K'] },
    aisle: { FIRST: [2,3,6], ECONOMY: [3,7] },  // después de qué columna va el pasillo
  },
  'B777-300ER': {
    engines: 2, length: '73.9m', wingspan: '64.8m',
    range: '13,650 km', cruiseSpeed: '905 km/h',
    seatsFirst: 10, seatsEconomy: 300, total: 310,
    firstRows: [1, 2], economyStartRow: 3,
    cols: { FIRST: ['A','B','C','D','E','F'], ECONOMY: ['A','B','C','D','E','F','G','H','J'] },
    aisle: { FIRST: [3], ECONOMY: [3,6] },
  },
  'A350-900': {
    engines: 2, length: '66.8m', wingspan: '64.75m',
    range: '15,000 km', cruiseSpeed: '903 km/h',
    seatsFirst: 12, seatsEconomy: 250, total: 262,
    firstRows: [1, 2], economyStartRow: 3,
    cols: { FIRST: ['A','B','C','D','E','F'], ECONOMY: ['A','B','C','D','E','F','G','H','J'] },
    aisle: { FIRST: [3], ECONOMY: [3,6] },
  },
  'B787-9': {
    engines: 2, length: '62.8m', wingspan: '60.1m',
    range: '14,140 km', cruiseSpeed: '903 km/h',
    seatsFirst: 8, seatsEconomy: 220, total: 228,
    firstRows: [1], economyStartRow: 2,
    cols: { FIRST: ['A','B','C','D','E','F','G','H'], ECONOMY: ['A','B','C','D','E','F','G','H'] },
    aisle: { FIRST: [3,5], ECONOMY: [3,6] },
  },
}

export const getAircraftModel = (aircraftId) => {
  const id = parseInt(aircraftId)
  if (id >= 1 && id <= 6) return 'A380-800'
  if (id >= 7 && id <= 24) return 'B777-300ER'
  if (id >= 25 && id <= 35) return 'A350-900'
  if (id >= 36 && id <= 50) return 'B787-9'
  return 'B777-300ER'
}

export const STATUS_COLORS = {
  AVAILABLE: '#3b82f6',
  RESERVED:  '#f59e0b',
  SOLD:      '#22c55e',
  LOCKED:    '#6b7280',
  REFUNDED:  '#ef4444',
}

export const STATUS_TEXT_COLORS = {
  AVAILABLE: 'text-blue-400',
  RESERVED:  'text-amber-400',
  SOLD:      'text-green-400',
  LOCKED:    'text-gray-400',
  REFUNDED:  'text-red-400',
}
