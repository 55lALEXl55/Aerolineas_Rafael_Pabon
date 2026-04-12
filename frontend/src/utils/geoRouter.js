// Dijkstra client-side para preview de rutas (el cálculo real está en ms-routes)
const AIRPORTS = {
  ATL: { name: 'Atlanta', lat: 33.64, lng: -84.43, node: 1 },
  LAX: { name: 'Los Angeles', lat: 33.94, lng: -118.41, node: 1 },
  DFW: { name: 'Dallas', lat: 32.9, lng: -97.04, node: 1 },
  SAO: { name: 'São Paulo', lat: -23.43, lng: -46.47, node: 1 },
  LON: { name: 'Londres', lat: 51.48, lng: -0.45, node: 2 },
  PAR: { name: 'París', lat: 49.0, lng: 2.55, node: 2 },
  FRA: { name: 'Fráncfort', lat: 50.05, lng: 8.57, node: 2 },
  IST: { name: 'Estambul', lat: 40.98, lng: 28.82, node: 2 },
  MAD: { name: 'Madrid', lat: 40.47, lng: -3.56, node: 2 },
  AMS: { name: 'Ámsterdam', lat: 52.31, lng: 4.77, node: 2 },
  DXB: { name: 'Dubái', lat: 25.25, lng: 55.36, node: 2 },
  PEK: { name: 'Pekín', lat: 40.08, lng: 116.58, node: 3 },
  TYO: { name: 'Tokio', lat: 35.55, lng: 139.78, node: 3 },
  SIN: { name: 'Singapur', lat: 1.36, lng: 103.99, node: 3 },
  CAN: { name: 'Guangzhou', lat: 23.39, lng: 113.3, node: 3 },
}

export const getAirportList = () =>
  Object.entries(AIRPORTS).map(([code, info]) => ({ code, ...info }))

export const getAirportName = (code) =>
  AIRPORTS[code]?.name || code

export const getAirportCoords = (code) => {
  const a = AIRPORTS[code]
  return a ? [a.lat, a.lng] : [0, 0]
}

export const getAirportNode = (code) =>
  AIRPORTS[code]?.node || 1

// Timezones aproximadas por aeropuerto
const TZ_MAP = {
  ATL: 'America/New_York', LAX: 'America/Los_Angeles', DFW: 'America/Chicago',
  SAO: 'America/Sao_Paulo', LON: 'Europe/London', PAR: 'Europe/Paris',
  FRA: 'Europe/Berlin', IST: 'Europe/Istanbul', MAD: 'Europe/Madrid',
  AMS: 'Europe/Amsterdam', DXB: 'Asia/Dubai', PEK: 'Asia/Shanghai',
  TYO: 'Asia/Tokyo', SIN: 'Asia/Singapore', CAN: 'Asia/Shanghai',
}

export const getAirportTz = (code) => TZ_MAP[code] || 'UTC'
