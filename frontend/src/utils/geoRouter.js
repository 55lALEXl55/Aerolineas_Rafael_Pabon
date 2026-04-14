// Dijkstra client-side para preview de rutas (el cálculo real está en ms-routes)
const AIRPORTS = {
  ATL: { name: 'Atlanta Hartsfield-Jackson', country: 'EE.UU.',   flag: '🇺🇸', lat: 33.64,  lng: -84.43,  node: 1, svgX: 18, svgY: 38 },
  LAX: { name: 'Los Ángeles Internacional',  country: 'EE.UU.',   flag: '🇺🇸', lat: 33.94,  lng: -118.41, node: 1, svgX: 10, svgY: 37 },
  DFW: { name: 'Dallas Fort Worth',          country: 'EE.UU.',   flag: '🇺🇸', lat: 32.9,   lng: -97.04,  node: 1, svgX: 15, svgY: 40 },
  SAO: { name: 'São Paulo Guarulhos',         country: 'Brasil',   flag: '🇧🇷', lat: -23.43, lng: -46.47,  node: 1, svgX: 30, svgY: 65 },
  LON: { name: 'Londres Heathrow',            country: 'R. Unido', flag: '🇬🇧', lat: 51.48,  lng: -0.45,   node: 2, svgX: 47, svgY: 25 },
  PAR: { name: 'París Charles de Gaulle',     country: 'Francia',  flag: '🇫🇷', lat: 49.0,   lng: 2.55,    node: 2, svgX: 48, svgY: 27 },
  FRA: { name: 'Fráncfort Internacional',     country: 'Alemania', flag: '🇩🇪', lat: 50.05,  lng: 8.57,    node: 2, svgX: 50, svgY: 26 },
  IST: { name: 'Estambul Aeropuerto',         country: 'Türkiye',  flag: '🇹🇷', lat: 40.98,  lng: 28.82,   node: 2, svgX: 56, svgY: 30 },
  MAD: { name: 'Madrid Barajas',              country: 'España',   flag: '🇪🇸', lat: 40.47,  lng: -3.56,   node: 2, svgX: 45, svgY: 30 },
  AMS: { name: 'Ámsterdam Schiphol',          country: 'P. Bajos', flag: '🇳🇱', lat: 52.31,  lng: 4.77,    node: 2, svgX: 49, svgY: 24 },
  DXB: { name: 'Dubái Internacional',         country: 'EAU',      flag: '🇦🇪', lat: 25.25,  lng: 55.36,   node: 2, svgX: 62, svgY: 38 },
  PEK: { name: 'Beijing Capital',             country: 'China',    flag: '🇨🇳', lat: 40.08,  lng: 116.58,  node: 3, svgX: 78, svgY: 30 },
  TYO: { name: 'Tokio Haneda',                country: 'Japón',    flag: '🇯🇵', lat: 35.55,  lng: 139.78,  node: 3, svgX: 83, svgY: 32 },
  SIN: { name: 'Singapur Changi',             country: 'Singapur', flag: '🇸🇬', lat: 1.36,   lng: 103.99,  node: 3, svgX: 76, svgY: 48 },
  CAN: { name: 'Guangzhou Baiyun',            country: 'China',    flag: '🇨🇳', lat: 23.39,  lng: 113.3,   node: 3, svgX: 78, svgY: 38 },
}

export const getAirportList = () =>
  Object.entries(AIRPORTS).map(([code, info]) => ({ code, ...info }))

export const getAirportName = (code) =>
  AIRPORTS[code]?.name || code

export const getAirportCoords = (code) => {
  const a = AIRPORTS[code]
  return a ? [a.lat, a.lng] : [0, 0]
}

export const getAirportSvgPos = (code) => {
  const a = AIRPORTS[code]
  return a ? { x: a.svgX, y: a.svgY } : { x: 50, y: 35 }
}

export const getAirportNode = (code) =>
  AIRPORTS[code]?.node || 1

export const getAirportFlag = (code) =>
  AIRPORTS[code]?.flag || ''

export const getAirportCountry = (code) =>
  AIRPORTS[code]?.country || ''

// Timezones aproximadas por aeropuerto
const TZ_MAP = {
  ATL: 'America/New_York', LAX: 'America/Los_Angeles', DFW: 'America/Chicago',
  SAO: 'America/Sao_Paulo', LON: 'Europe/London', PAR: 'Europe/Paris',
  FRA: 'Europe/Berlin', IST: 'Europe/Istanbul', MAD: 'Europe/Madrid',
  AMS: 'Europe/Amsterdam', DXB: 'Asia/Dubai', PEK: 'Asia/Shanghai',
  TYO: 'Asia/Tokyo', SIN: 'Asia/Singapore', CAN: 'Asia/Shanghai',
}

export const getAirportTz = (code) => TZ_MAP[code] || 'UTC'
