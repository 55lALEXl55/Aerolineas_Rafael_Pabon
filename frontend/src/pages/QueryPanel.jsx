import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronUp, Search, Download } from 'lucide-react'
import dayjs from 'dayjs'
import { queryFlights, querySeats, queryTickets, queryRevenue, querySync } from '../api'
import { epochToLocal, dateToEpoch } from '../utils/epochUtils'

const CATEGORIES = [
  {
    id: 'flights', label: 'Vuelos', fn: queryFlights,
    filters: [
      { name: 'origin', label: 'Origen', type: 'text', placeholder: 'ATL' },
      { name: 'destination', label: 'Destino', type: 'text', placeholder: 'TYO' },
      { name: 'status', label: 'Estado', type: 'select', options: ['', 'SCHEDULED','BOARDING','IN_FLIGHT','LANDED','ARRIVED','DELAYED'] },
      { name: 'date_from', label: 'Desde', type: 'date' },
      { name: 'date_to', label: 'Hasta', type: 'date' },
      { name: 'node_id', label: 'Nodo', type: 'select', options: ['', '1', '2', '3'] },
    ],
    columns: ['flight_id', 'flight_number', 'origin', 'destination', 'status', 'departure_epoch', 'price_economy'],
  },
  {
    id: 'seats', label: 'Asientos', fn: querySeats,
    filters: [
      { name: 'flight_id', label: 'ID Vuelo', type: 'text' },
      { name: 'status', label: 'Estado', type: 'select', options: ['', 'AVAILABLE','RESERVED','SOLD','LOCKED','REFUNDED'] },
      { name: 'seat_class', label: 'Clase', type: 'select', options: ['', 'FIRST', 'ECONOMY'] },
    ],
    columns: ['seat_id', 'flight_id', 'seat_number', 'seat_class', 'status', 'price'],
  },
  {
    id: 'tickets', label: 'Tickets', fn: queryTickets,
    filters: [
      { name: 'passport', label: 'Pasaporte', type: 'text' },
      { name: 'status', label: 'Estado', type: 'select', options: ['', 'ACTIVE','REFUNDED','CANCELLED'] },
      { name: 'date_from', label: 'Desde', type: 'date' },
      { name: 'date_to', label: 'Hasta', type: 'date' },
    ],
    columns: ['ticket_id', 'flight_number', 'seat_number', 'passenger_name', 'passport_number', 'status', 'created_at'],
  },
  {
    id: 'revenue', label: 'Ingresos', fn: queryRevenue,
    filters: [
      { name: 'date_from', label: 'Desde', type: 'date' },
      { name: 'date_to', label: 'Hasta', type: 'date' },
      { name: 'node_id', label: 'Nodo', type: 'select', options: ['', '1', '2', '3'] },
      { name: 'seat_class', label: 'Clase', type: 'select', options: ['', 'FIRST', 'ECONOMY'] },
    ],
    columns: ['route', 'total_revenue', 'first_revenue', 'economy_revenue', 'ticket_count'],
  },
  {
    id: 'sync', label: 'Sincronización', fn: querySync,
    filters: [
      { name: 'node_id', label: 'Nodo', type: 'select', options: ['', '1', '2', '3'] },
      { name: 'event_type', label: 'Tipo', type: 'text' },
      { name: 'date_from', label: 'Desde', type: 'date' },
    ],
    columns: ['event_id', 'node_id', 'event_type', 'timestamp', 'vector_clock', 'lamport_ts'],
  },
]

const PER_PAGE = 20

function CategoryPanel({ cat }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({})
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [page, setPage] = useState(1)

  const handleQuery = async () => {
    setLoading(true)
    setError('')
    try {
      const params = { ...form }
      // Convert date fields to epoch
      for (const key of ['date_from', 'date_to']) {
        if (params[key]) params[key] = dateToEpoch(params[key])
      }
      // Remove empty
      Object.keys(params).forEach(k => !params[k] && delete params[k])
      const data = await cat.fn(params)
      setResults(Array.isArray(data) ? data : data.results || data.items || [])
      setPage(1)
    } catch (e) {
      setError(e.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const exportCsv = () => {
    if (!results.length) return
    const cols = cat.columns
    const rows = results.map(r => cols.map(c => r[c] ?? '').join(','))
    const csv = [cols.join(','), ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${cat.id}_${Date.now()}.csv`; a.click()
  }

  const paged = results.slice((page - 1) * PER_PAGE, page * PER_PAGE)
  const totalPages = Math.ceil(results.length / PER_PAGE)

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 hover:bg-slate-750 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Search className="w-4 h-4 text-blue-400" />
          <span className="text-white font-semibold">{cat.label}</span>
          {results.length > 0 && (
            <span className="bg-blue-600 text-white text-xs px-2 py-0.5 rounded-full">{results.length}</span>
          )}
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>

      {open && (
        <div className="border-t border-slate-700">
          {/* Filters */}
          <div className="p-5 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {cat.filters.map(f => (
              <div key={f.name}>
                <label className="text-slate-400 text-xs block mb-1">{f.label}</label>
                {f.type === 'select' ? (
                  <select
                    value={form[f.name] || ''}
                    onChange={e => setForm(p => ({ ...p, [f.name]: e.target.value }))}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-white text-sm
                      focus:outline-none focus:border-blue-500"
                  >
                    {f.options.map(o => <option key={o} value={o}>{o || 'Todos'}</option>)}
                  </select>
                ) : (
                  <input
                    type={f.type}
                    value={form[f.name] || ''}
                    onChange={e => setForm(p => ({ ...p, [f.name]: e.target.value }))}
                    placeholder={f.placeholder}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-white text-sm
                      focus:outline-none focus:border-blue-500"
                  />
                )}
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3 px-5 pb-4">
            <button onClick={handleQuery} disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm
                flex items-center gap-2 transition-colors disabled:opacity-50">
              <Search className="w-3.5 h-3.5" />
              {loading ? 'Consultando...' : 'Consultar'}
            </button>
            {results.length > 0 && (
              <button onClick={exportCsv}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm
                  flex items-center gap-2 transition-colors">
                <Download className="w-3.5 h-3.5" />
                Exportar CSV
              </button>
            )}
            {error && <span className="text-red-400 text-sm">{error}</span>}
          </div>

          {/* Results table */}
          {results.length > 0 && (
            <div className="border-t border-slate-700">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-700 bg-slate-900/50">
                      {cat.columns.map(c => (
                        <th key={c} className="text-left px-4 py-2.5 text-slate-400 font-medium">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {paged.map((row, i) => (
                      <tr key={i} className="border-b border-slate-700/30 hover:bg-slate-700/30">
                        {cat.columns.map(c => (
                          <td key={c} className="px-4 py-2 text-slate-300 font-mono">
                            {c.includes('epoch') || c === 'timestamp' || c === 'created_at'
                              ? epochToLocal(row[c])
                              : String(row[c] ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 p-3">
                  <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                    className="px-3 py-1 rounded bg-slate-700 text-slate-300 text-xs disabled:opacity-50">←</button>
                  <span className="text-slate-400 text-xs">{page} / {totalPages}</span>
                  <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                    className="px-3 py-1 rounded bg-slate-700 text-slate-300 text-xs disabled:opacity-50">→</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function QueryPanel() {
  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-white mb-1">Panel de Consultas Avanzadas</h1>
        <p className="text-slate-400 text-sm">8 categorías de consultas distribuidas · Exportación CSV</p>
      </div>
      {CATEGORIES.map(cat => <CategoryPanel key={cat.id} cat={cat} />)}
    </div>
  )
}
