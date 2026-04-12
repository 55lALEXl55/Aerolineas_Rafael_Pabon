# SKILL — Frontend React + Vite + TailwindCSS
# Usar cuando: crear o modificar cualquier componente del frontend

## Stack
React 18, Vite, TailwindCSS, Zustand, Recharts, Leaflet, react-i18next, Fuse.js, day.js

## Reglas críticas de fechas
```js
// CORRECTO — recibir epoch del backend y enmascarar
import dayjs from 'dayjs'
const mostrarFecha = (epoch) => dayjs.unix(epoch).format('DD MMM YYYY HH:mm')
const mostrarHora = (epoch) => dayjs.unix(epoch).format('HH:mm')

// INCORRECTO — NUNCA manipular fechas en frontend
const fecha = new Date()  // PROHIBIDO enviar al backend
```

## Estructura de componentes
```
frontend/src/
├── pages/
│   ├── FlightSearch.jsx      # búsqueda con fuzzy search
│   ├── SeatSelection.jsx     # mapa visual del avión
│   ├── FlightDashboard.jsx   # dashboard por vuelo
│   ├── CompanyDashboard.jsx  # dashboard gerencial
│   ├── TicketView.jsx        # boleto generado
│   └── QueryPanel.jsx        # panel de consultas
├── components/
│   ├── SeatMap/
│   │   ├── A380SeatMap.jsx   # 449 asientos — filas A-F col 1-29 + primera 01-03
│   │   ├── B777SeatMap.jsx   # 310 asientos
│   │   ├── A350SeatMap.jsx   # 262 asientos
│   │   └── B787SeatMap.jsx   # 228 asientos
│   ├── BookingModal.jsx
│   ├── SyncStatus.jsx        # semáforo verde/amarillo/rojo
│   └── NodeIndicator.jsx     # qué nodo está usando el usuario
├── i18n/
│   ├── es.json  en.json  zh.json  pt.json  ar.json
├── utils/
│   ├── epochUtils.js         # formatear epoch → legible
│   ├── geoRouter.js          # ciudad → nodo
│   └── seatLayout.js         # layout de asientos por modelo
└── stores/
    ├── bookingStore.js       # estado de reserva activa
    └── syncStore.js          # estado de sincronización
```

## Colores de asientos (TailwindCSS)
```
AVAILABLE  → bg-blue-500 hover:bg-blue-400
RESERVED   → bg-yellow-400 hover:bg-yellow-300
SOLD       → bg-green-600
REFUNDED   → bg-red-500
LOCKED     → bg-gray-400 cursor-not-allowed
```

## Patrón de llamada a la API
```js
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost'

export const api = {
  flights: {
    search: (params) => fetch(`${API_BASE}/api/flights/search?${new URLSearchParams(params)}`).then(r => r.json()),
    getSeats: (flightId) => fetch(`${API_BASE}/api/flights/${flightId}/seats`).then(r => r.json()),
  },
  bookings: {
    lock: (seatId, sessionToken) => fetch(`${API_BASE}/api/bookings/lock`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ seat_id: seatId, session_token: sessionToken })
    }).then(r => r.json()),
    reserve: (data) => fetch(`${API_BASE}/api/bookings/reserve`, { method: 'POST', ... }),
    buy: (data) => fetch(`${API_BASE}/api/bookings/buy`, { method: 'POST', ... }),
  }
}
```

## Zustand store — patrón
```js
import { create } from 'zustand'

export const useBookingStore = create((set, get) => ({
  selectedFlight: null,
  selectedSeat: null,
  sessionToken: crypto.randomUUID(),
  purchaseCity: null,
  activeNode: null,

  setFlight: (flight) => set({ selectedFlight: flight }),
  setSeat: (seat) => set({ selectedSeat: seat }),
  setPurchaseCity: (city) => set({
    purchaseCity: city,
    activeNode: determineNode(city)
  }),
  reset: () => set({ selectedFlight: null, selectedSeat: null }),
}))
```

## geoRouter.js — determinar nodo por ciudad
```js
const AMERICA_AIRPORTS = ['ATL', 'LAX', 'DFW', 'SAO']
const EUROPE_AIRPORTS = ['LON', 'PAR', 'FRA', 'IST', 'MAD', 'AMS', 'DXB']
const ASIA_AIRPORTS = ['PEK', 'TYO', 'SIN', 'CAN']

// Para ciudades (del API mundial):
const AMERICA_COUNTRIES = ['US','CA','MX','BR','AR','CO','PE','CL','VE','BO', ...]
const EUROPE_COUNTRIES = ['GB','FR','DE','ES','IT','NL','PT','BE','CH','AT', ...]

export const determineNode = (city) => {
  // Usar coordenadas de la ciudad para determinar continente
  if (city.longitude < -30) return 1  // América
  if (city.longitude < 60) return 2   // Europa/África/MO
  return 3                             // Asia/Oceanía
}
```

## Fuzzy search de vuelos — NUNCA dropdown
```js
import Fuse from 'fuse.js'

const fuse = new Fuse(flights, {
  keys: ['origin', 'destination', 'flight_id'],
  threshold: 0.3,
})

// Input con debounce 300ms → fuse.search(query)
```

## i18n — patrón
```js
import { useTranslation } from 'react-i18next'

const MyComponent = () => {
  const { t } = useTranslation()
  return <button>{t('booking.reserve')}</button>
}
```

## SyncStatus widget — obligatorio en header
```jsx
// Verde: delay < 3s, Amarillo: 3-7s, Rojo: >7s
const SyncStatus = () => {
  const { delay, conflicts } = useSyncStore()
  const color = delay < 3000 ? 'green' : delay < 7000 ? 'yellow' : 'red'
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full bg-${color}-500`} />
      <span className="text-xs">{delay}ms</span>
      {conflicts > 0 && <span className="text-xs text-orange-500">{conflicts} conflictos</span>}
    </div>
  )
}
```
