import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Search, MapPin, Calendar, ArrowLeftRight, Clock } from 'lucide-react'
import Fuse from 'fuse.js'
import dayjs from 'dayjs'
import { searchFlights, findRoute } from '../api'
import { getAirportList, getAirportName } from '../utils/geoRouter'
import { dateToEpoch, epochToDate, durationStr } from '../utils/epochUtils'
import FlightCard from '../components/FlightCard'
import { useBookingStore } from '../stores/bookingStore'

const AIRPORTS = getAirportList()
const fuse = new Fuse(AIRPORTS, { keys: ['code', 'name'], threshold: 0.3 })

const NODE_COLORS = { 1: 'bg-blue-600', 2: 'bg-purple-600', 3: 'bg-orange-500' }
const NODE_LABELS = { 1: 'DB1 · América', 2: 'DB2 · Europa', 3: 'DB3 · Asia' }

function AirportInput({ label, value, onChange, placeholder }) {
  const [query, setQuery] = useState(value || '')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const ref = useRef()

  useEffect(() => {
    const handler = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleInput = (v) => {
    setQuery(v)
    const r = v.length > 0 ? fuse.search(v).slice(0, 8).map(x => x.item) : AIRPORTS.slice(0, 8)
    setResults(r)
    setOpen(true)
  }

  const select = (airport) => {
    setQuery(`${airport.code} — ${airport.name}`)
    onChange(airport.code)
    setOpen(false)
  }

  return (
    <div ref={ref} className="relative">
      <label className="text-slate-400 text-xs block mb-1">{label}</label>
      <div className="flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 focus-within:border-blue-500">
        <MapPin className="w-4 h-4 text-slate-500 shrink-0" />
        <input
          value={query}
          onChange={e => handleInput(e.target.value)}
          onFocus={() => handleInput(query)}
          placeholder={placeholder}
          className="bg-transparent text-white flex-1 outline-none text-sm"
        />
      </div>
      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 bg-slate-800 border border-slate-700 rounded-lg mt-1 z-30 shadow-xl overflow-hidden">
          {results.map(a => (
            <button
              key={a.code}
              onMouseDown={() => select(a)}
              className="w-full flex items-center gap-3 px-3 py-2 hover:bg-slate-700 text-left"
            >
              <span className={`text-xs px-1.5 py-0.5 rounded font-mono font-bold ${NODE_COLORS[a.node]} text-white`}>
                {a.code}
              </span>
              <span className="text-white text-sm">{a.name}</span>
              <span className="text-slate-500 text-xs ml-auto">{NODE_LABELS[a.node]}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function FlightSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { setSelectedFlight } = useBookingStore()

  const [form, setForm] = useState({
    origin: '',
    destination: '',
    date: dayjs().add(1, 'day').format('YYYY-MM-DD'),
    cls: 'ECONOMY',
  })
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searched, setSearched] = useState(false)

  const swap = () => setForm(f => ({ ...f, origin: f.destination, destination: f.origin }))

  const handleSearch = async () => {
    if (!form.origin || !form.destination) {
      setError('Selecciona origen y destino')
      return
    }
    if (form.origin === form.destination) {
      setError('El origen y destino deben ser diferentes')
      return
    }
    setLoading(true)
    setError('')
    setSearched(true)
    try {
      const epoch = dateToEpoch(form.date)
      const data = await searchFlights(form.origin, form.destination, epoch, form.cls)
      setResults(Array.isArray(data) ? data : data.flights || [])
    } catch (e) {
      // Fallback to route finding
      try {
        const route = await findRoute(form.origin, form.destination, epoch, 'price')
        setResults(route.flights || [])
      } catch {
        setError(e.message)
        setResults([])
      }
    } finally {
      setLoading(false)
    }
  }

  const handleFlightClick = (flight) => {
    setSelectedFlight(flight)
    navigate(`/flights/${flight.flight_id}/seats`)
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Hero */}
      <div className="text-center py-8">
        <h1 className="text-4xl font-bold text-white mb-2">✈ Aerolíneas Rafael Pabón</h1>
        <p className="text-slate-400">Sistema distribuido · 3 nodos · 60,000 vuelos</p>
      </div>

      {/* Search form */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AirportInput
            label={t('flight.origin')}
            value={form.origin}
            onChange={v => setForm(f => ({ ...f, origin: v }))}
            placeholder="ATL — Atlanta"
          />
          {/* Swap button */}
          <div className="hidden md:flex items-end pb-2 justify-start">
            <button onClick={swap}
              className="p-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white transition-colors"
              title="Intercambiar">
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>
          <AirportInput
            label={t('flight.destination')}
            value={form.destination}
            onChange={v => setForm(f => ({ ...f, destination: v }))}
            placeholder="TYO — Tokio"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
          {/* Date */}
          <div>
            <label className="text-slate-400 text-xs block mb-1">{t('flight.date')}</label>
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 focus-within:border-blue-500">
              <Calendar className="w-4 h-4 text-slate-500 shrink-0" />
              <input
                type="date"
                value={form.date}
                min={dayjs().format('YYYY-MM-DD')}
                onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
                className="bg-transparent text-white flex-1 outline-none text-sm"
              />
            </div>
          </div>

          {/* Class */}
          <div>
            <label className="text-slate-400 text-xs block mb-1">{t('flight.class')}</label>
            <select
              value={form.cls}
              onChange={e => setForm(f => ({ ...f, cls: e.target.value }))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-blue-500"
            >
              <option value="ECONOMY">{t('seat.economy')}</option>
              <option value="FIRST">{t('seat.first')}</option>
            </select>
          </div>

          {/* Search button */}
          <div className="flex items-end">
            <button
              onClick={handleSearch}
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold
                flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              <Search className="w-4 h-4" />
              {loading ? t('flight.searching') : t('flight.search')}
            </button>
          </div>
        </div>

        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
      </div>

      {/* Results */}
      {searched && !loading && (
        <div>
          {results.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Search className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>{t('flight.no_results')}</p>
              <p className="text-xs mt-1">Intenta con otra fecha o ruta con escala</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-white font-semibold">{results.length} vuelos encontrados</h2>
                <span className="text-slate-400 text-sm">
                  {form.origin} → {form.destination} · {epochToDate(dateToEpoch(form.date))}
                </span>
              </div>
              {results.map(f => (
                <FlightCard key={f.flight_id} flight={f} onClick={handleFlightClick} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Node indicators */}
      <div className="grid grid-cols-3 gap-4 pt-4">
        {[
          { key: 'DB1', label: 'América', airports: 'ATL LAX DFW SAO', color: 'border-blue-700 bg-blue-900/20' },
          { key: 'DB2', label: 'Europa + ME', airports: 'LON PAR FRA IST MAD AMS DXB', color: 'border-purple-700 bg-purple-900/20' },
          { key: 'DB3', label: 'Asia + Oceanía', airports: 'PEK TYO SIN CAN', color: 'border-orange-700 bg-orange-900/20' },
        ].map(n => (
          <div key={n.key} className={`border rounded-xl p-4 ${n.color}`}>
            <div className="font-bold text-white text-sm">{n.key} · {n.label}</div>
            <div className="text-slate-400 text-xs mt-1 font-mono">{n.airports}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
