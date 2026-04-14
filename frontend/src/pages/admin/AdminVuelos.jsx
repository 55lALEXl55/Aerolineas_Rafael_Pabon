import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getAllFlights } from '../../api'
import { epochToDate, epochToTime } from '../../utils/epochUtils'
import { getAircraftModel } from '../../utils/seatLayout'
import { useTranslation } from 'react-i18next'
import { Search, RefreshCw, List, Plane, ChevronLeft, ChevronRight } from 'lucide-react'
import NodeSelector from '../../components/NodeSelector'

const STATUS_BADGE = {
  SCHEDULED: 'bg-blue-900/40 text-blue-400 border-blue-800',
  BOARDING:   'bg-green-900/40 text-green-400 border-green-800',
  IN_FLIGHT:  'bg-cyan-900/40 text-cyan-400 border-cyan-800',
  ARRIVED:    'bg-slate-700 text-slate-400 border-slate-600',
  DEPARTED:   'bg-purple-900/40 text-purple-400 border-purple-800',
  CANCELLED:  'bg-red-900/40 text-red-400 border-red-800',
  DELAYED:    'bg-yellow-900/40 text-yellow-400 border-yellow-800',
}

export default function AdminVuelos() {
  const { t } = useTranslation()
  const [flights, setFlights] = useState([])
  const [loading, setLoading] = useState(true)
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const PER_PAGE = 20

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (origin)      params.set('origin', origin.toUpperCase())
      if (destination) params.set('destination', destination.toUpperCase())
      if (status)      params.set('status', status)
      params.set('limit', '200')
      const data = await getAllFlights(params.toString())
      setFlights(Array.isArray(data) ? data : [])
      setPage(1)
    } catch {
      setFlights([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const paged = flights.slice((page - 1) * PER_PAGE, page * PER_PAGE)
  const totalPages = Math.ceil(flights.length / PER_PAGE)

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <List className="w-6 h-6 text-purple-400" />
            Gestión de Vuelos
          </h1>
          <p className="text-slate-400 text-sm">{flights.length.toLocaleString()} vuelos · 3 bases de datos</p>
        </div>
        <NodeSelector compact />
      </div>

      {/* Filters */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="text-slate-400 text-xs block mb-1">Origen</label>
            <input value={origin} onChange={e => setOrigin(e.target.value)}
              placeholder="ATL"
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white text-sm
                uppercase focus:outline-none focus:border-blue-500 font-mono" maxLength={3} />
          </div>
          <div>
            <label className="text-slate-400 text-xs block mb-1">Destino</label>
            <input value={destination} onChange={e => setDestination(e.target.value)}
              placeholder="TYO"
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white text-sm
                uppercase focus:outline-none focus:border-blue-500 font-mono" maxLength={3} />
          </div>
          <div>
            <label className="text-slate-400 text-xs block mb-1">Estado</label>
            <select value={status} onChange={e => setStatus(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white text-sm
                focus:outline-none focus:border-blue-500">
              <option value="">Todos</option>
              {['SCHEDULED','BOARDING','IN_FLIGHT','ARRIVED','DEPARTED','CANCELLED','DELAYED'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={load} disabled={loading}
              className="w-full py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium
                flex items-center justify-center gap-2 transition-colors disabled:opacity-50">
              <Search className="w-4 h-4" />
              {loading ? 'Buscando...' : 'Buscar'}
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-500">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
            Cargando vuelos...
          </div>
        ) : paged.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <Plane className="w-8 h-8 mx-auto mb-2 opacity-30" />
            Sin vuelos encontrados
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-900/50">
                    {['#', 'Vuelo', 'Ruta', 'Salida', 'Llegada', 'Duración', 'Avión', 'Precio', 'Estado', 'Acción'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-slate-400 font-medium text-xs">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {paged.map((f, i) => {
                    const model = getAircraftModel(f.aircraft_id)
                    const st = f.status || 'SCHEDULED'
                    return (
                      <tr key={f.flight_id}
                        className="border-b border-slate-700/30 hover:bg-slate-700/20 transition-colors">
                        <td className="px-4 py-3 text-slate-500 font-mono text-xs">{f.flight_id}</td>
                        <td className="px-4 py-3 text-blue-400 font-mono font-semibold">{f.flight_number}</td>
                        <td className="px-4 py-3">
                          <span className="text-white font-bold">{f.origin}</span>
                          <span className="text-slate-500 mx-1">→</span>
                          <span className="text-white font-bold">{f.destination}</span>
                        </td>
                        <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                          {epochToTime(f.departure_epoch)}<br/>
                          <span className="text-slate-500">{epochToDate(f.departure_epoch)}</span>
                        </td>
                        <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                          {epochToTime(f.arrival_epoch)}
                        </td>
                        <td className="px-4 py-3 text-slate-400 text-xs font-mono">
                          {f.duration_minutes ? `${Math.floor(f.duration_minutes/60)}h ${f.duration_minutes%60}m` : '—'}
                        </td>
                        <td className="px-4 py-3 text-slate-400 text-xs">{model}</td>
                        <td className="px-4 py-3 text-blue-400 font-semibold">
                          ${f.price_economy ?? f.economy_price ?? '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-block px-2 py-0.5 rounded border text-xs font-medium
                            ${STATUS_BADGE[st] || 'bg-slate-700 text-slate-400 border-slate-600'}`}>
                            {st}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <Link to={`/vuelo/${f.flight_id}/asientos`}
                            className="text-xs text-blue-400 hover:text-blue-300 underline transition-colors">
                            Ver asientos
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
                <span className="text-slate-400 text-xs">
                  {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, flights.length)} de {flights.length}
                </span>
                <div className="flex items-center gap-2">
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                    className="p-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300
                      disabled:opacity-40 transition-colors">
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-slate-400 text-xs">{page} / {totalPages}</span>
                  <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                    className="p-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300
                      disabled:opacity-40 transition-colors">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
