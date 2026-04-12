import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Users, DollarSign, RefreshCw } from 'lucide-react'
import Fuse from 'fuse.js'
import { getAllFlights, getFlightSeats, getFlightTickets } from '../api'
import { epochToLocal } from '../utils/epochUtils'
import { STATUS_TEXT_COLORS } from '../utils/seatLayout'
import SeatMap from '../components/SeatMap/SeatMap'

export default function FlightDashboard() {
  const { id } = useParams()
  const { t } = useTranslation()

  const [flights, setFlights] = useState([])
  const [selectedFlight, setSelectedFlight] = useState(null)
  const [seats, setSeats] = useState([])
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [filtered, setFiltered] = useState([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [page, setPage] = useState(1)
  const PER_PAGE = 15

  useEffect(() => { loadFlights() }, [])

  useEffect(() => {
    if (!selectedFlight) return
    loadSeatsAndTickets()
    const interval = setInterval(loadSeats, 5000)
    return () => clearInterval(interval)
  }, [selectedFlight])

  useEffect(() => {
    if (!flights.length) return
    const f = new Fuse(flights, { keys: ['flight_number', 'origin', 'destination'], threshold: 0.3 })
    const r = query.length > 0 ? f.search(query).map(x => x.item) : flights.slice(0, 10)
    setFiltered(r)
  }, [query, flights])

  async function loadFlights() {
    try {
      const data = await getAllFlights('limit=500')
      setFlights(Array.isArray(data) ? data : data.flights || [])
    } catch { /* ignore */ }
  }

  async function loadSeatsAndTickets() {
    setLoading(true)
    try {
      const [s, tk] = await Promise.all([
        getFlightSeats(selectedFlight.flight_id),
        getFlightTickets(selectedFlight.flight_id),
      ])
      setSeats(Array.isArray(s) ? s : s.seats || [])
      setTickets(Array.isArray(tk) ? tk : tk.tickets || [])
    } catch { /* ignore */ }
    setLoading(false)
  }

  async function loadSeats() {
    if (!selectedFlight) return
    try {
      const s = await getFlightSeats(selectedFlight.flight_id)
      setSeats(Array.isArray(s) ? s : s.seats || [])
    } catch { /* ignore */ }
  }

  const stats = seats.reduce((acc, s) => { acc[s.status] = (acc[s.status] || 0) + 1; return acc }, {})
  const revenue = {
    first: seats.filter(s => s.seat_class === 'FIRST' && s.status === 'SOLD').reduce((a, s) => a + s.price, 0),
    economy: seats.filter(s => s.seat_class === 'ECONOMY' && s.status === 'SOLD').reduce((a, s) => a + s.price, 0),
  }

  const pagedTickets = tickets.slice((page - 1) * PER_PAGE, page * PER_PAGE)
  const totalPages = Math.ceil(tickets.length / PER_PAGE)

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard de Vuelo</h1>

      {/* Flight selector */}
      <div className="relative">
        <input
          value={query}
          onChange={e => { setQuery(e.target.value); setShowDropdown(true) }}
          onFocus={() => setShowDropdown(true)}
          placeholder="Buscar vuelo (número, origen, destino)..."
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-white
            focus:outline-none focus:border-blue-500"
        />
        {showDropdown && filtered.length > 0 && (
          <div className="absolute top-full left-0 right-0 bg-slate-800 border border-slate-700 rounded-lg mt-1 z-20
            shadow-xl max-h-60 overflow-y-auto">
            {filtered.map(f => (
              <button
                key={f.flight_id}
                onMouseDown={() => { setSelectedFlight(f); setQuery(f.flight_number); setShowDropdown(false) }}
                className="w-full flex items-center gap-3 px-4 py-2 hover:bg-slate-700 text-left"
              >
                <span className="font-mono text-blue-400">{f.flight_number}</span>
                <span className="text-white text-sm">{f.origin} → {f.destination}</span>
                <span className={`ml-auto text-xs ${STATUS_TEXT_COLORS[f.status] || 'text-slate-400'}`}>{f.status}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedFlight && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { k: 'AVAILABLE', l: 'Libres',     c: 'text-blue-400',  bg: 'bg-blue-900/20 border-blue-800' },
              { k: 'RESERVED',  l: 'Reservados', c: 'text-amber-400', bg: 'bg-amber-900/20 border-amber-800' },
              { k: 'SOLD',      l: 'Vendidos',   c: 'text-green-400', bg: 'bg-green-900/20 border-green-800' },
              { k: 'LOCKED',    l: 'Bloqueados', c: 'text-gray-400',  bg: 'bg-gray-900/20 border-gray-700' },
            ].map(({ k, l, c, bg }) => (
              <div key={k} className={`border rounded-xl p-4 text-center ${bg}`}>
                <div className={`text-3xl font-bold ${c}`}>{stats[k] || 0}</div>
                <div className="text-xs text-slate-400 mt-1">{l}</div>
              </div>
            ))}
          </div>

          {/* Revenue */}
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
              <div className="text-slate-400 text-xs mb-1">Primera Clase</div>
              <div className="text-amber-400 font-bold text-xl">${revenue.first.toLocaleString()}</div>
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
              <div className="text-slate-400 text-xs mb-1">Turista</div>
              <div className="text-blue-400 font-bold text-xl">${revenue.economy.toLocaleString()}</div>
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
              <div className="text-slate-400 text-xs mb-1">Total</div>
              <div className="text-white font-bold text-xl">${(revenue.first + revenue.economy).toLocaleString()}</div>
            </div>
          </div>

          {/* Seat map */}
          <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-slate-700 flex items-center justify-between">
              <h3 className="text-white font-semibold">Mapa de asientos en tiempo real</h3>
              <button onClick={loadSeats} className="text-slate-400 hover:text-white">
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
            {loading ? (
              <div className="h-32 flex items-center justify-center text-slate-500">Cargando...</div>
            ) : (
              <SeatMap aircraftId={selectedFlight.aircraft_id} seats={seats} />
            )}
          </div>

          {/* Passenger table */}
          <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-slate-700">
              <h3 className="text-white font-semibold">Pasajeros del vuelo ({tickets.length})</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    {['Asiento', 'Nombre', 'Pasaporte', 'Tipo', 'Estado', 'Fecha'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-slate-400 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pagedTickets.map((tk, i) => (
                    <tr key={i} className="border-b border-slate-700/50 hover:bg-slate-750">
                      <td className="px-4 py-2 font-mono text-blue-400">{tk.seat_number}</td>
                      <td className="px-4 py-2 text-white">{tk.passenger_name || '—'}</td>
                      <td className="px-4 py-2 font-mono text-slate-300">{tk.passport_number || '—'}</td>
                      <td className="px-4 py-2 text-slate-300">{tk.ticket_type || '—'}</td>
                      <td className="px-4 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${STATUS_TEXT_COLORS[tk.status] || 'text-slate-400'}`}>
                          {t(`status.${tk.status}`, tk.status)}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-slate-400 text-xs">{epochToLocal(tk.created_at)}</td>
                    </tr>
                  ))}
                  {tickets.length === 0 && (
                    <tr><td colSpan={6} className="text-center py-8 text-slate-500">Sin pasajeros</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 p-4">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="px-3 py-1 rounded bg-slate-700 text-slate-300 text-sm disabled:opacity-50">←</button>
                <span className="text-slate-400 text-sm">{page} / {totalPages}</span>
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                  className="px-3 py-1 rounded bg-slate-700 text-slate-300 text-sm disabled:opacity-50">→</button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
