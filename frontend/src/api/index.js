const BASE = import.meta.env.VITE_API_URL || ''

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

// ─── Flights ──────────────────────────────────────────────────────────────────
export const searchFlights = (origin, destination, dateEpoch, cls) =>
  req(`/api/flights/search?origin=${origin}&destination=${destination}&date_epoch=${dateEpoch}&seat_class=${cls}`)

export const getFlightSeats = (flightId) =>
  req(`/api/flights/${flightId}/seats`)

export const getFlightById = (flightId) =>
  req(`/api/flights/${flightId}`)

export const getAllFlights = (params = '') =>
  req(`/api/flights?${params}`)

// ─── Bookings ─────────────────────────────────────────────────────────────────
export const generateToken = () =>
  (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`

export const lockSeat = (flightId, seatId, sessionToken) =>
  req(`/api/bookings/lock`, {
    method: 'POST',
    body: JSON.stringify({
      flight_id: flightId,
      seat_id: seatId,
      session_token: sessionToken || generateToken(),
    }),
  })

export const reserveSeat = (data) =>
  req(`/api/bookings/reserve`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const buySeat = (data) =>
  req(`/api/bookings/purchase`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

// refundTicket / cancelReservation: the frontend only has ticket_id at call time.
// These use dedicated endpoints that look up seat/flight by ticket_id server-side.
export const refundTicket = (ticketId) =>
  req(`/api/bookings/refund-ticket`, {
    method: 'POST',
    body: JSON.stringify({ ticket_id: ticketId }),
  })

export const cancelReservation = (ticketId) =>
  req(`/api/bookings/cancel-ticket`, {
    method: 'POST',
    body: JSON.stringify({ ticket_id: ticketId }),
  })

export const getPassengerByPassport = (passport) =>
  req(`/api/bookings/passenger/${passport}`)

// ─── Routes / Dijkstra ────────────────────────────────────────────────────────
// mode: 'price' | 'time'  (backend accepts those two values)
// dateEpoch: required by backend; defaults to today 00:00 UTC if omitted
export const findRoute = (origin, destination, dateEpoch, mode = 'price', seatClass = 'ECONOMY') => {
  const epoch = dateEpoch || Math.floor(new Date().setUTCHours(0, 0, 0, 0) / 1000)
  const m = (mode === 'cheapest' || mode === 'price') ? 'price' : 'time'
  return req(`/api/routes/shortest?origin=${origin}&destination=${destination}&date_epoch=${epoch}&mode=${m}&seat_class=${seatClass}`)
}

export const getAirports = () =>
  req(`/api/routes/all-airports`)

// ─── Tickets ──────────────────────────────────────────────────────────────────
export const getTicket = (ticketId) =>
  req(`/api/tickets/${ticketId}`)

export const getFlightTickets = (flightId) =>
  req(`/api/tickets/flight/${flightId}`)

export const getTicketsByPassport = (passport) =>
  req(`/api/tickets/passenger/${passport}`)

// ─── Dashboard ────────────────────────────────────────────────────────────────
export const getDashboardStats = () =>
  req(`/api/dashboard/overview`)

export const getDashboardRevenue = () =>
  req(`/api/dashboard/revenue-by-route`)

export const getDashboardFleetStatus = () =>
  req(`/api/dashboard/fleet-status`)

export const getDashboardSyncStatus = () =>
  req(`/api/dashboard/sync/status`)

export const getDashboardSyncLog = () =>
  req(`/api/dashboard/sync/log`)

export const getDashboardTopRoutes = () =>
  req(`/api/dashboard/top-flights`)

export const getDashboardFlightStatus = () =>
  req(`/api/dashboard/flights-by-status`)

export const searchPassenger = (passport) =>
  req(`/api/bookings/passenger/${passport}`)

// ─── Query Panel ──────────────────────────────────────────────────────────────
export const queryFlights = (params) =>
  req(`/api/flights?${new URLSearchParams(params)}`)

export const querySeats = (params) =>
  req(`/api/flights/seats/query?${new URLSearchParams(params)}`)

export const queryTickets = (params) =>
  req(`/api/tickets?${new URLSearchParams(params)}`)

export const queryRevenue = (_params) =>
  req(`/api/dashboard/revenue-by-route`)

export const querySync = (_params) =>
  req(`/api/dashboard/sync/log`)
