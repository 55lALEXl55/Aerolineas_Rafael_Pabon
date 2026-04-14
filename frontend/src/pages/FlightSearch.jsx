import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Search, Calendar, ArrowLeftRight, Clock, Tag, DollarSign, Plane, ChevronDown } from 'lucide-react'
import dayjs from 'dayjs'
import { searchFlights, findRoute, getDatasetInfo } from '../api'
import { getAirportList, getAirportName, getAirportFlag } from '../utils/geoRouter'
import { epochToTime, durationStr } from '../utils/epochUtils'
import { getAircraftModel } from '../utils/seatLayout'
import { useBookingStore } from '../stores/bookingStore'
import NodeSelector from '../components/NodeSelector'
import FlightMapModal from '../components/FlightMapModal'

const ALL_AIRPORTS = getAirportList()

const NODE_TAG = {
  1: { label: 'DB1', cls: 'bg-blue-700 text-blue-100' },
  2: { label: 'DB2', cls: 'bg-purple-700 text-purple-100' },
  3: { label: 'DB3', cls: 'bg-orange-700 text-orange-100' },
}

// ─── Airport combobox ─────────────────────────────────────────────────────────
function AirportCombobox({ label, value, onChange, exclude }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const ref = useRef()
  const inputRef = useRef()

  const filtered = ALL_AIRPORTS
    .filter(a => a.code !== exclude)
    .filter(a => {
      if (!query) return true
      const q = query.toLowerCase()
      return a.code.toLowerCase().includes(q) || a.name.toLowerCase().includes(q) || a.country.toLowerCase().includes(q)
    })
    .slice(0, 10)

  const selected = ALL_AIRPORTS.find(a => a.code === value)

  const handleSelect = (airport) => {
    onChange(airport.code)
    setQuery('')
    setOpen(false)
  }

  const handleBlur = (e) => {
    if (!ref.current?.contains(e.relatedTarget)) setOpen(false)
  }

  return (
    <div ref={ref} className="relative" onBlur={handleBlur}>
      <label className="text-slate-400 text-xs block mb-1">{label}</label>
      <button
        onClick={() => { setOpen(!open); setTimeout(() => inputRef.current?.focus(), 50) }}
        className={`w-full flex items-center gap-2 bg-slate-900 border rounded-xl px-3 py-2.5 text-left
          transition-colors focus:outline-none
          ${open ? 'border-blue-500' : 'border-slate-700 hover:border-slate-500'}`}
      >
        {selected ? (
          <>
            <span className="text-lg leading-none">{selected.flag}</span>
            <div className="flex-1 min-w-0">
              <div className="text-white font-semibold text-sm">{selected.code}</div>
              <div className="text-slate-400 text-xs truncate">{selected.name}</div>
            </div>
            <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${NODE_TAG[selected.node].cls}`}>
              {NODE_TAG[selected.node].label}
            </span>
          </>
        ) : (
          <>
            <Plane className="w-4 h-4 text-slate-500 shrink-0" />
            <span className="text-slate-500 text-sm flex-1">Seleccionar aeropuerto</span>
            <ChevronDown className="w-4 h-4 text-slate-500" />
          </>
        )}
      </button>

      {open && (
        <div className="absolute top-full left-0 right-0 bg-slate-800 border border-slate-700
          rounded-xl mt-1 z-40 shadow-2xl overflow-hidden">
          <div className="p-2 border-b border-slate-700">
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Buscar ciudad o código..."
              className="w-full bg-slate-900 text-white text-sm px-3 py-1.5 rounded-lg
                focus:outline-none focus:ring-1 focus:ring-blue-500 placeholder-slate-500"
            />
          </div>
          <div className="max-h-56 overflow-y-auto">
            {filtered.map(a => (
              <button
                key={a.code}
                tabIndex={0}
                onMouseDown={() => handleSelect(a)}
                className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-slate-700
                  transition-colors text-left border-b border-slate-700/30 last:border-0"
              >
                <span className="text-xl leading-none">{a.flag}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-bold text-sm">{a.code}</span>
                    <span className="text-slate-400 text-xs truncate">{a.name}</span>
                  </div>
                  <div className="text-slate-500 text-xs">{a.country}</div>
                </div>
                <span className={`text-xs px-1.5 py-0.5 rounded font-mono shrink-0 ${NODE_TAG[a.node].cls}`}>
                  {NODE_TAG[a.node].label}
                </span>
              </button>
            ))}
            {filtered.length === 0 && (
              <div className="px-4 py-6 text-center text-slate-500 text-sm">Sin resultados</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Route card (direct or connecting) ───────────────────────────────────────
function RouteCard({ route, onClick, delay = 0 }) {
  const { t } = useTranslation()
  const flights = route.flights || []
  const first = flights[0]
  const last  = flights[flights.length - 1]
  if (!first) return null

  const stops = [first.origin, ...flights.map(f => f.destination)]
  const stopovers = stops.slice(1, -1)
  const model = getAircraftModel(first.aircraft_id)

  return (
    <div
      onClick={() => onClick(route)}
      style={{ animationDelay: `${delay}ms` }}
      className="bg-slate-800 border border-slate-700 rounded-xl p-4 cursor-pointer
        hover:border-blue-500 hover:bg-slate-750 transition-all duration-200
        hover:shadow-lg hover:shadow-blue-900/20 animate-[fadeSlideUp_0.3s_ease-out_both]
        group"
    >
      <div className="flex items-center justify-between gap-4">
        {/* Route visualization */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="text-center shrink-0">
            <div className="text-2xl font-bold text-white">{first.origin}</div>
            <div className="text-xs text-slate-400">{getAirportFlag(first.origin)}</div>
            <div className="text-xs text-slate-500 font-mono">{epochToTime(first.departure_epoch)}</div>
          </div>

          <div className="flex-1 flex flex-col items-center min-w-0">
            <div className="w-full flex items-center gap-1">
              <div className="flex-1 h-px bg-gradient-to-r from-slate-600 to-blue-600/50" />
              {stopovers.map((s, i) => (
                <div key={i} className="flex items-center gap-1">
                  <div className="w-2 h-2 rounded-full bg-amber-400 border-2 border-slate-800 shrink-0" />
                  <div className="flex-1 h-px bg-gradient-to-r from-amber-600/50 to-blue-600/50" />
                </div>
              ))}
              <Plane className="w-4 h-4 text-blue-400 shrink-0 group-hover:text-blue-300 transition-colors" />
              <div className="flex-1 h-px bg-gradient-to-r from-blue-600/50 to-slate-600" />
            </div>
            <div className="text-xs text-slate-500 mt-1">
              {durationStr(route.total_minutes || first.duration_minutes, t)}
            </div>
            {stopovers.length > 0 ? (
              <div className="text-xs text-amber-400 font-medium">
                vía {stopovers.join(', ')}
              </div>
            ) : (
              <div className="text-xs text-green-400">Directo</div>
            )}
          </div>

          <div className="text-center shrink-0">
            <div className="text-2xl font-bold text-white">{last.destination}</div>
            <div className="text-xs text-slate-400">{getAirportFlag(last.destination)}</div>
            <div className="text-xs text-slate-500 font-mono">{epochToTime(last.arrival_epoch)}</div>
          </div>
        </div>

        {/* Price + info */}
        <div className="text-right shrink-0">
          <div className="text-3xl font-bold text-blue-400">
            ${(route.total_cost ?? first.price_economy ?? 0).toLocaleString()}
          </div>
          <div className="text-xs text-slate-400">{model}</div>
          <div className="text-xs text-slate-500">{first.flight_number}</div>
        </div>
      </div>
    </div>
  )
}

// ─── Skeleton card ─────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 animate-pulse">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4 flex-1">
          <div className="space-y-2">
            <div className="h-7 w-12 bg-slate-700 rounded" />
            <div className="h-3 w-16 bg-slate-700 rounded" />
          </div>
          <div className="flex-1 h-px bg-slate-700" />
          <div className="space-y-2">
            <div className="h-7 w-12 bg-slate-700 rounded" />
            <div className="h-3 w-16 bg-slate-700 rounded" />
          </div>
        </div>
        <div className="space-y-2">
          <div className="h-8 w-20 bg-slate-700 rounded" />
          <div className="h-3 w-16 bg-slate-700 rounded" />
        </div>
      </div>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function FlightSearch() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { setSelectedFlight, activeNode } = useBookingStore()

  const [datasetRange, setDatasetRange] = useState({
    start_date: '2026-03-25',
    end_date: '2026-04-05',
  })
  const [form, setForm] = useState({
    origin: '',
    destination: '',
    date: '2026-03-25',
    cls: 'ECONOMY',
  })
  const [cheapest, setCheapest] = useState([])
  const [fastest,  setFastest]  = useState([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [searched, setSearched] = useState(false)
  const [mapRoute, setMapRoute] = useState(null)

  // Cargar rango de fechas del dataset activo
  useEffect(() => {
    getDatasetInfo()
      .then(info => {
        if (info?.date_range) {
          setDatasetRange(info.date_range)
          setForm(f => ({ ...f, date: info.date_range.start_date }))
        }
      })
      .catch(() => {/* fallback a valores por defecto */})
  }, [])

  const swap = () => setForm(f => ({ ...f, origin: f.destination, destination: f.origin }))

  // Wrap a direct flight as a route object
  const toRoute = (f) => ({
    total_cost: f.price_economy || f.economy_price || 0,
    total_minutes: f.duration_minutes || 0,
    flights: [f],
  })

  const handleSearch = async () => {
    if (!form.origin || !form.destination) { setError('Selecciona origen y destino'); return }
    if (form.origin === form.destination)   { setError('El origen y destino deben ser diferentes'); return }

    setLoading(true)
    setError('')
    setSearched(true)
    setCheapest([])
    setFastest([])

    const epoch = Math.floor(new Date(form.date + 'T00:00:00Z').getTime() / 1000)

    try {
      // Run all queries in parallel
      const [directRes, routePrice, routeTime] = await Promise.allSettled([
        searchFlights(form.origin, form.destination, epoch, form.cls),
        findRoute(form.origin, form.destination, epoch, 'price', form.cls),
        findRoute(form.origin, form.destination, epoch, 'time',  form.cls),
      ])

      // Collect all candidate routes
      const directFlights = (directRes.status === 'fulfilled')
        ? (Array.isArray(directRes.value) ? directRes.value : directRes.value?.flights || [])
        : []

      const directRoutes = directFlights.map(toRoute)

      const priceRoute = routePrice.status === 'fulfilled' && routePrice.value?.flights?.length
        ? [routePrice.value]
        : []
      const timeRoute = routeTime.status === 'fulfilled' && routeTime.value?.flights?.length
        ? [routeTime.value]
        : []

      const allRoutes = [...directRoutes, ...priceRoute, ...timeRoute]

      if (allRoutes.length === 0) {
        setError('')
        setCheapest([])
        setFastest([])
        setLoading(false)
        return
      }

      // Deduplicate by first flight_id
      const seen = new Set()
      const unique = []
      for (const r of allRoutes) {
        const key = r.flights?.[0]?.flight_id ?? JSON.stringify(r.flights?.map(f => f.flight_id))
        if (!seen.has(key)) { seen.add(key); unique.push(r) }
      }

      // Sort and take top 2 for each category
      const byCheap = [...unique].sort((a, b) => (a.total_cost ?? 0) - (b.total_cost ?? 0)).slice(0, 2)
      const byFast  = [...unique].sort((a, b) => (a.total_minutes ?? 0) - (b.total_minutes ?? 0)).slice(0, 2)

      setCheapest(byCheap)
      setFastest(byFast)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleRouteClick = (route) => {
    setMapRoute(route)
  }

  const handleSelectRoute = (route) => {
    const flight = route.flights?.[0]
    if (!flight) return
    setSelectedFlight(flight)
    setMapRoute(null)
    navigate(`/vuelo/${flight.flight_id}/asientos`)
  }

  const NODE_LABELS = { 1: 'DB1 — América 🌎', 2: 'DB2 — Europa/MO 🌍', 3: 'DB3 — Asia 🌏' }
  const NODE_COLORS = { 1: 'text-blue-400', 2: 'text-purple-400', 3: 'text-orange-400' }

  const hasCheap = cheapest.length > 0
  const hasFast  = fastest.length > 0
  const noResults = searched && !loading && !hasCheap && !hasFast

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      {/* Hero */}
      <div className="text-center py-6">
        <h1 className="text-5xl font-extrabold text-white mb-2 tracking-tight">
          ✈ Aerolíneas Rafael Pabón
        </h1>
        <p className="text-slate-400">Sistema distribuido · 3 nodos · 60,000 vuelos</p>
      </div>

      {/* Node selector */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-slate-400 text-xs mb-1">Conectado a:</p>
            <p className={`font-semibold text-sm ${NODE_COLORS[activeNode]}`}>{NODE_LABELS[activeNode]}</p>
          </div>
          <NodeSelector />
        </div>
      </div>

      {/* Search form */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-xl shadow-black/20">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-end mb-4">
          <AirportCombobox
            label={t('flight.origin')}
            value={form.origin}
            onChange={v => setForm(f => ({ ...f, origin: v }))}
            exclude={form.destination}
          />
          <button
            onClick={swap}
            className="p-2.5 rounded-xl bg-slate-700 hover:bg-slate-600 text-slate-300
              hover:text-white transition-all hover:rotate-180 duration-300 mb-0.5"
            title="Intercambiar"
          >
            <ArrowLeftRight className="w-4 h-4" />
          </button>
          <AirportCombobox
            label={t('flight.destination')}
            value={form.destination}
            onChange={v => setForm(f => ({ ...f, destination: v }))}
            exclude={form.origin}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Date */}
          <div>
            <label className="text-slate-400 text-xs block mb-1">
              {t('flight.date')}
              <span className="ml-2 text-yellow-400 text-xs font-normal">
                {dayjs(datasetRange.start_date).format('D MMM')} – {dayjs(datasetRange.end_date).format('D MMM YYYY')}
              </span>
            </label>
            <div className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5
              focus-within:border-blue-500 transition-colors">
              <Calendar className="w-4 h-4 text-slate-500 shrink-0" />
              <input
                type="date"
                value={form.date}
                min={datasetRange.start_date}
                max={datasetRange.end_date}
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
              className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2.5 text-white text-sm
                outline-none focus:border-blue-500 transition-colors cursor-pointer"
            >
              <option value="ECONOMY">🪑 {t('seat.economy')}</option>
              <option value="FIRST">👑 {t('seat.first')}</option>
            </select>
          </div>

          {/* Search */}
          <div className="flex items-end">
            <button
              onClick={handleSearch}
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold
                flex items-center justify-center gap-2 transition-all hover:shadow-lg hover:shadow-blue-900/40
                disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Search className="w-4 h-4" />
              {loading ? 'Buscando...' : t('flight.search')}
            </button>
          </div>
        </div>

        {error && <p className="text-red-400 text-sm mt-3 bg-red-900/20 px-3 py-2 rounded-lg">{error}</p>}
      </div>

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-3">
          {[0, 1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Results */}
      {!loading && searched && (
        <div className="space-y-6">
          {noResults && (
            <div className="text-center py-16 text-slate-500">
              <Search className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="text-lg">{t('flight.no_results')}</p>
              <p className="text-sm mt-1 text-slate-600">Intenta otra fecha o par de ciudades</p>
            </div>
          )}

          {/* 2 Cheapest */}
          {hasCheap && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <DollarSign className="w-5 h-5 text-green-400" />
                <h2 className="text-white font-semibold text-lg">Más económicas</h2>
                <span className="text-slate-500 text-sm">— Ordenadas por precio</span>
              </div>
              <div className="space-y-3">
                {cheapest.map((r, i) => (
                  <RouteCard key={i} route={r} onClick={handleRouteClick} delay={i * 60} />
                ))}
              </div>
            </div>
          )}

          {/* 2 Fastest */}
          {hasFast && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-5 h-5 text-blue-400" />
                <h2 className="text-white font-semibold text-lg">Más rápidas</h2>
                <span className="text-slate-500 text-sm">— Ordenadas por duración</span>
              </div>
              <div className="space-y-3">
                {fastest.map((r, i) => (
                  <RouteCard key={i} route={r} onClick={handleRouteClick} delay={i * 60 + 120} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Flight map modal */}
      {mapRoute && (
        <FlightMapModal
          route={mapRoute}
          onClose={() => setMapRoute(null)}
          onSelect={handleSelectRoute}
        />
      )}
    </div>
  )
}
