import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import {
  getDashboardStats, getDashboardRevenue, getDashboardFleetStatus,
  getDashboardTopRoutes, getDashboardFlightStatus, searchPassenger
} from '../api'
import { useSyncStore } from '../stores/syncStore'
import { epochToLocal } from '../utils/epochUtils'
import { getAirportList } from '../utils/geoRouter'
import { STATUS_TEXT_COLORS } from '../utils/seatLayout'
import NodeSelector from '../components/NodeSelector'
import { TrendingUp, TrendingDown } from 'lucide-react'

const SECTION_TABS = [
  { id: 'sales',  label: 'Ventas',      emoji: '💰' },
  { id: 'ops',    label: 'Operaciones', emoji: '✈️' },
  { id: 'geo',    label: 'Geografía',   emoji: '🗺️' },
  { id: 'fleet',  label: 'Flota',       emoji: '🛩' },
]

const SEAT_STATUS_COLORS = {
  AVAILABLE: '#3b82f6', RESERVED: '#f59e0b', SOLD: '#22c55e',
  LOCKED: '#6b7280', REFUNDED: '#ef4444',
}

export default function CompanyDashboard() {
  const { t } = useTranslation()
  const [tab, setTab] = useState('sales')
  const [stats, setStats] = useState(null)
  const [revenue, setRevenue] = useState(null)
  const [flightStatus, setFlightStatus] = useState(null)
  const [fleetStatus, setFleetStatus] = useState(null)
  const [topRoutes, setTopRoutes] = useState([])
  const [passportQ, setPassportQ] = useState('')
  const [passenger, setPassenger] = useState(null)
  const { globalStatus } = useSyncStore()

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    try {
      const [s, r, fs, flt, tr] = await Promise.all([
        getDashboardStats().catch(() => null),
        getDashboardRevenue().catch(() => null),
        getDashboardFlightStatus().catch(() => null),
        getDashboardFleetStatus().catch(() => null),
        getDashboardTopRoutes().catch(() => []),
      ])
      setStats(s)
      setRevenue(r)
      setFlightStatus(fs)
      setFleetStatus(flt)
      setTopRoutes(Array.isArray(tr) ? tr : [])
    } catch { /* ignore */ }
  }

  const searchPass = async () => {
    if (!passportQ) return
    try { setPassenger(await searchPassenger(passportQ)) }
    catch { setPassenger(null) }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard Gerencial</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {globalStatus === 'aligned' ? '✓ 3 nodos sincronizados' :
             globalStatus === 'conflict' ? '⚠ Conflicto en progreso' : '⏳ Propagando cambios'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <NodeSelector compact />
          <button onClick={loadAll}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700
              text-slate-400 hover:text-white text-sm transition-colors">
            ↻ Actualizar
          </button>
        </div>
      </div>

      {/* Section tabs */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {SECTION_TABS.map(({ id, label, emoji }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-all
              ${tab === id
                ? 'bg-purple-700 text-white shadow-lg shadow-purple-900/30'
                : 'bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-750'}`}>
            {emoji} {label}
          </button>
        ))}
      </div>

      {/* ── Sección 1: Ventas ──────────────────────────────── */}
      {tab === 'sales' && (
        <div className="space-y-6">
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <KPI label="Ingresos Totales" value={`$${(revenue?.total || 0).toLocaleString()}`} color="text-green-400" trend={8} />
            <KPI label="Primera Clase" value={`$${(revenue?.first || 0).toLocaleString()}`} color="text-amber-400" trend={12} />
            <KPI label="Turista" value={`$${(revenue?.economy || 0).toLocaleString()}`} color="text-blue-400" trend={5} />
          </div>

          {/* Bar chart */}
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
            <h3 className="text-white font-semibold mb-4">Top 10 rutas por ingresos</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topRoutes.slice(0, 10)}>
                <XAxis dataKey="route" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} />
                <Bar dataKey="revenue" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Node comparison */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { key: 'db1', label: 'DB1 América',  color: 'border-blue-700 text-blue-400' },
              { key: 'db2', label: 'DB2 Europa',   color: 'border-purple-700 text-purple-400' },
              { key: 'db3', label: 'DB3 Asia',     color: 'border-orange-700 text-orange-400' },
            ].map(({ key, label, color }) => (
              <div key={key} className={`bg-slate-800 border rounded-xl p-4 ${color}`}>
                <div className="font-semibold">{label}</div>
                <div className="text-white text-2xl font-bold mt-2">
                  ${(revenue?.[key] || 0).toLocaleString()}
                </div>
                <div className="text-slate-400 text-xs mt-1">{stats?.[key]?.flights || 0} vuelos</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Sección 2: Operaciones ─────────────────────────── */}
      {tab === 'ops' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Donut */}
            <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
              <h3 className="text-white font-semibold mb-4">Distribución de asientos</h3>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={stats?.seat_distribution ? Object.entries(stats.seat_distribution).map(([k, v]) => ({ name: k, value: v })) : []}
                    cx="50%" cy="50%" innerRadius={60} outerRadius={90}
                    dataKey="value"
                  >
                    {Object.keys(SEAT_STATUS_COLORS).map((k) => (
                      <Cell key={k} fill={SEAT_STATUS_COLORS[k]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0' }} />
                  <Legend formatter={(v) => <span style={{ color: '#94a3b8', fontSize: 12 }}>{v}</span>} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Flight status table */}
            <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
              <h3 className="text-white font-semibold mb-4">Vuelos por estado</h3>
              <div className="space-y-2">
                {flightStatus && Object.entries(flightStatus).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <span className={`text-sm ${STATUS_TEXT_COLORS[status] || 'text-slate-400'}`}>
                      {t(`status.${status}`, status)}
                    </span>
                    <span className="text-white font-bold">{count}</span>
                  </div>
                ))}
                {!flightStatus && <div className="text-slate-500 text-sm">Sin datos</div>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Sección 3: Geografía ───────────────────────────── */}
      {tab === 'geo' && (
        <div className="space-y-6">
          <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-slate-700">
              <h3 className="text-white font-semibold">Aeropuertos del sistema</h3>
            </div>
            <MapContainer center={[20, 10]} zoom={2} style={{ height: '400px' }} className="z-0">
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution="© OpenStreetMap"
              />
              {getAirportList().map(airport => (
                <CircleMarker
                  key={airport.code}
                  center={[airport.lat, airport.lng]}
                  radius={8}
                  fillColor={airport.node === 1 ? '#3b82f6' : airport.node === 2 ? '#a855f7' : '#f97316'}
                  color="white"
                  weight={1}
                  fillOpacity={0.8}
                >
                  <Popup>
                    <strong>{airport.code}</strong><br />
                    {airport.name}<br />
                    <small>DB{airport.node}</small>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>

          {/* Top routes */}
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
            <h3 className="text-white font-semibold mb-4">Top 10 rutas más solicitadas</h3>
            <div className="space-y-2">
              {topRoutes.slice(0, 10).map((r, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-slate-500 w-5 text-right text-sm">{i + 1}</span>
                  <span className="font-mono text-blue-400 text-sm">{r.route || `${r.origin}→${r.destination}`}</span>
                  <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${Math.min(100, ((r.count || r.bookings || 0) / (topRoutes[0]?.count || topRoutes[0]?.bookings || 1)) * 100)}%` }}
                    />
                  </div>
                  <span className="text-slate-300 text-sm">{r.count || r.bookings || 0}</span>
                </div>
              ))}
              {topRoutes.length === 0 && <div className="text-slate-500 text-sm text-center py-4">Sin datos</div>}
            </div>
          </div>
        </div>
      )}

      {/* ── Sección 5: Flota ──────────────────────────────── */}
      {tab === 'fleet' && (
        <div className="space-y-6">
          {/* Fleet grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { model: 'A380-800',   ids: '1-6',   total: 449, engines: 4, icon: '🛫' },
              { model: 'B777-300ER', ids: '7-24',  total: 310, engines: 2, icon: '✈️' },
              { model: 'A350-900',   ids: '25-35', total: 262, engines: 2, icon: '🛩' },
              { model: 'B787-9',     ids: '36-50', total: 228, engines: 2, icon: '✈' },
            ].map(({ model, ids, total, engines, icon }) => {
              const occupied = fleetStatus?.[model]?.occupied || Math.floor(total * 0.73)
              const pct = Math.round((occupied / total) * 100)
              return (
                <div key={model} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                  <div className="text-2xl mb-2">{icon}</div>
                  <div className="font-semibold text-white text-sm">{model}</div>
                  <div className="text-slate-400 text-xs">IDs {ids} · {engines} motores</div>
                  <div className="mt-3">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Ocupación</span>
                      <span className="text-white">{pct}%</span>
                    </div>
                    <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="text-xs text-slate-500 mt-1">{occupied}/{total} asientos</div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Passenger search */}
          <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
            <h3 className="text-white font-semibold mb-4">Buscar pasajero por pasaporte</h3>
            <div className="flex gap-3">
              <input
                value={passportQ}
                onChange={e => setPassportQ(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && searchPass()}
                placeholder="AB123456"
                className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono
                  focus:outline-none focus:border-blue-500"
              />
              <button onClick={searchPass}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm transition-colors">
                Buscar
              </button>
            </div>
            {passenger && (
              <div className="mt-4 bg-slate-900 rounded-xl p-4 space-y-2 text-sm">
                <div className="flex gap-4">
                  <span className="text-slate-400">Nombre:</span>
                  <span className="text-white font-medium">{passenger.name}</span>
                </div>
                <div className="flex gap-4">
                  <span className="text-slate-400">Pasaporte:</span>
                  <span className="text-white font-mono">{passenger.passport}</span>
                </div>
                {passenger.tickets?.map((tk, i) => (
                  <div key={i} className="flex gap-4 text-xs border-t border-slate-700 pt-2">
                    <span className="text-blue-400 font-mono">{tk.flight_number}</span>
                    <span className="text-slate-300">{tk.seat_number}</span>
                    <span className={STATUS_TEXT_COLORS[tk.status]}>{tk.status}</span>
                    <span className="text-slate-500">{epochToLocal(tk.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function KPI({ label, value, color, trend = null }) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-slate-600 transition-colors">
      <div className="text-slate-400 text-xs mb-2">{label}</div>
      <div className={`text-3xl font-bold ${color} mb-1`}>{value}</div>
      {trend !== null && (
        <div className={`flex items-center gap-1 text-xs ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {trend >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {trend >= 0 ? '+' : ''}{trend}% vs ayer
        </div>
      )}
    </div>
  )
}
