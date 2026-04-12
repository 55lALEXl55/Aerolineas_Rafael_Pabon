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
  req(`/api/flights/search?origin=${origin}&destination=${destination}&departure_epoch=${dateEpoch}&class=${cls}`)

export const getFlightSeats = (flightId) =>
  req(`/api/flights/${flightId}/seats`)

export const getFlightById = (flightId) =>
  req(`/api/flights/${flightId}`)

export const getAllFlights = (params = '') =>
  req(`/api/flights?${params}`)

// ─── Bookings ─────────────────────────────────────────────────────────────────
export const lockSeat = (flightId, seatId) =>
  req(`/api/bookings/lock`, {
    method: 'POST',
    body: JSON.stringify({ flight_id: flightId, seat_id: seatId }),
  })

export const reserveSeat = (data) =>
  req(`/api/bookings/reserve`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const buySeat = (data) =>
  req(`/api/bookings/buy`, {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const refundTicket = (ticketId) =>
  req(`/api/bookings/${ticketId}/refund`, { method: 'POST' })

export const cancelReservation = (bookingId) =>
  req(`/api/bookings/${bookingId}/cancel`, { method: 'POST' })

export const getPassengerByPassport = (passport) =>
  req(`/api/bookings/passenger/${passport}`)

// ─── Routes / Dijkstra ────────────────────────────────────────────────────────
export const findRoute = (origin, destination, mode = 'cheapest') =>
  req(`/api/routes/find?origin=${origin}&destination=${destination}&mode=${mode}`)

export const getAirports = () =>
  req(`/api/routes/airports`)

// ─── Tickets ──────────────────────────────────────────────────────────────────
export const getTicket = (ticketId) =>
  req(`/api/tickets/${ticketId}`)

export const getFlightTickets = (flightId) =>
  req(`/api/tickets/flight/${flightId}`)

// ─── Dashboard ────────────────────────────────────────────────────────────────
export const getDashboardStats = () =>
  req(`/api/dashboard/stats`)

export const getDashboardRevenue = () =>
  req(`/api/dashboard/revenue`)

export const getDashboardFleetStatus = () =>
  req(`/api/dashboard/fleet`)

export const getDashboardSyncStatus = () =>
  req(`/api/dashboard/sync/status`)

export const getDashboardSyncLog = () =>
  req(`/api/dashboard/sync/log`)

export const getDashboardTopRoutes = () =>
  req(`/api/dashboard/routes/top`)

export const getDashboardFlightStatus = () =>
  req(`/api/dashboard/flights/status`)

export const searchPassenger = (passport) =>
  req(`/api/dashboard/passenger/${passport}`)

// ─── Query Panel ──────────────────────────────────────────────────────────────
export const queryFlights = (params) =>
  req(`/api/flights/query?${new URLSearchParams(params)}`)

export const querySeats = (params) =>
  req(`/api/flights/seats/query?${new URLSearchParams(params)}`)

export const queryTickets = (params) =>
  req(`/api/tickets/query?${new URLSearchParams(params)}`)

export const queryRevenue = (params) =>
  req(`/api/dashboard/revenue/query?${new URLSearchParams(params)}`)

export const querySync = (params) =>
  req(`/api/dashboard/sync/query?${new URLSearchParams(params)}`)
