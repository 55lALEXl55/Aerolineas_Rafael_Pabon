import { useState, useEffect, useRef } from 'react'
import { getDashboardSyncStatus, getDashboardSyncLog } from '../../api'
import { useSyncStore } from '../../stores/syncStore'
import { epochToLocal } from '../../utils/epochUtils'
import { Activity, RefreshCw, AlertTriangle, CheckCircle, Clock, Zap, Database, Map, RotateCcw, Terminal, Pause, Play } from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL || ''

const LEVEL_STYLES = {
  ERROR:    'text-red-400',
  WARNING:  'text-yellow-400',
  WARN:     'text-yellow-400',
  INFO:     'text-green-400',
  DEBUG:    'text-cyan-400',
}
const LEVEL_DOT = {
  ERROR: 'bg-red-500', WARNING: 'bg-yellow-400', WARN: 'bg-yellow-400',
  INFO: 'bg-green-400', DEBUG: 'bg-cyan-400',
}
const SERVICE_COLORS = {
  'ms-flights':   'text-blue-400',
  'ms-bookings':  'text-purple-400',
  'ms-routes':    'text-green-400',
  'ms-sync':      'text-yellow-400',
  'ms-tickets':   'text-orange-400',
  'ms-dashboard': 'text-pink-400',
}

function LiveLogs() {
  const [logs, setLogs] = useState([])
  const [nextIndex, setNextIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const [filter, setFilter] = useState('')
  const containerRef = useRef(null)
  const intervalRef = useRef(null)

  const fetchLogs = async (idx) => {
    try {
      const res = await fetch(`${BASE}/api/sync/logs-stream?since=${idx}`)
      if (!res.ok) return idx
      const data = await res.json()
      if (data.logs?.length) {
        setLogs(prev => [...prev, ...data.logs].slice(-300))
        return data.next_index
      }
      return data.next_index ?? idx
    } catch {
      return idx
    }
  }

  useEffect(() => {
    let idx = 0
    const poll = async () => {
      if (!paused) idx = await fetchLogs(idx)
      setNextIndex(idx)
    }
    poll()
    intervalRef.current = setInterval(poll, 2000)
    return () => clearInterval(intervalRef.current)
  }, [paused])

  useEffect(() => {
    if (!paused && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs, paused])

  const visible = filter
    ? logs.filter(l =>
        (l.message || '').toLowerCase().includes(filter.toLowerCase()) ||
        (l.service || '').toLowerCase().includes(filter.toLowerCase())
      )
    : logs

  const clearLogs = () => setLogs([])

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-800">
        <h3 className="text-white font-semibold flex items-center gap-2 text-sm">
          <Terminal className="w-4 h-4 text-green-400" />
          LiveLogs — Microservicios
          <span className="text-xs bg-green-900/40 text-green-400 px-1.5 py-0.5 rounded-full font-mono">
            polling 2s
          </span>
          {!paused && <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />}
        </h3>
        <div className="flex items-center gap-2">
          <input
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Filtrar..."
            className="text-xs bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-slate-300
              focus:outline-none focus:border-blue-500 w-32"
          />
          <button
            onClick={() => setPaused(p => !p)}
            className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors
              ${paused ? 'bg-green-700 text-white' : 'bg-slate-700 text-slate-300 hover:text-white'}`}
          >
            {paused ? <><Play className="w-3 h-3" /> Reanudar</> : <><Pause className="w-3 h-3" /> Pausar</>}
          </button>
          <button
            onClick={clearLogs}
            className="px-2 py-1 rounded-lg text-xs text-slate-400 hover:text-white bg-slate-700 hover:bg-slate-600 transition-colors"
          >
            Limpiar
          </button>
        </div>
      </div>

      {/* Log stream */}
      <div ref={containerRef} className="h-64 overflow-y-auto font-mono text-xs p-3 space-y-0.5">
        {visible.length === 0 && (
          <div className="text-slate-600 text-center py-8">
            {logs.length === 0 ? 'Esperando logs de microservicios...' : 'Sin resultados para el filtro'}
          </div>
        )}
        {visible.map((log, i) => {
          const level = (log.level || 'INFO').toUpperCase()
          const svc   = log.service || '?'
          const ts    = log.timestamp
            ? new Date(log.timestamp * 1000).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : '—'
          return (
            <div key={i} className="flex items-start gap-2 leading-relaxed hover:bg-slate-800/50 rounded px-1 py-0.5">
              <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${LEVEL_DOT[level] || 'bg-slate-500'}`} />
              <span className="text-slate-600 shrink-0 w-20">{ts}</span>
              <span className={`shrink-0 w-28 ${SERVICE_COLORS[svc] || 'text-slate-400'}`}>{svc}</span>
              <span className={`shrink-0 w-14 ${LEVEL_STYLES[level] || 'text-slate-400'}`}>[{level}]</span>
              <span className="text-slate-300 break-all">{log.message || '—'}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const getGraphStatus = (epoch) =>
  fetch(`${BASE}/api/routes/graph-status${epoch ? `?date_epoch=${epoch}` : ''}`)
    .then(r => r.json()).catch(() => null)

const NODE_CFG = [
  { key: 'db1', id: 1, label: 'DB1 América',   tech: 'SQL Server 2022', emoji: '🌎', color: 'blue',   borderCls: 'border-blue-700',   badgeCls: 'bg-blue-700 text-blue-100',   ringCls: 'ring-blue-500' },
  { key: 'db2', id: 2, label: 'DB2 Europa',    tech: 'SQL Server 2022', emoji: '🌍', color: 'purple', borderCls: 'border-purple-700', badgeCls: 'bg-purple-700 text-purple-100', ringCls: 'ring-purple-500' },
  { key: 'db3', id: 3, label: 'DB3 Asia',      tech: 'MongoDB 7',       emoji: '🌏', color: 'orange', borderCls: 'border-orange-700', badgeCls: 'bg-orange-700 text-orange-100', ringCls: 'ring-orange-500' },
]

const DOT_COLOR = {
  green: 'bg-green-400', yellow: 'bg-yellow-400', red: 'bg-red-500', gray: 'bg-gray-500',
}

function NodeCard({ cfg, nodeData, getNodeColor }) {
  const delay   = nodeData?.delay_ms || 0
  const lamport = nodeData?.lamport_ts || 0
  const vector  = nodeData?.vector_clock || '[0,0,0]'
  const flights = nodeData?.flight_count || 0
  const lastSync = nodeData?.last_sync_ago || '—'
  const conflicts = nodeData?.conflict_count || 0
  const dot = getNodeColor(cfg.key)

  return (
    <div className={`bg-slate-800 border-2 ${cfg.borderCls} rounded-2xl p-5 flex flex-col gap-4
      transition-all duration-300 hover:shadow-xl`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className={`w-3 h-3 rounded-full ${DOT_COLOR[dot]} ${dot !== 'green' ? 'animate-pulse' : ''}`} />
            <span className="text-white font-bold">{cfg.emoji} {cfg.label}</span>
          </div>
          <div className="text-slate-400 text-xs">{cfg.tech}</div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded font-mono font-bold ${cfg.badgeCls}`}>
          Node {cfg.id}
        </span>
      </div>

      {/* Lamport + Vector */}
      <div className="bg-slate-900 rounded-xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-slate-500 text-xs">Lamport</span>
          <span className="text-cyan-400 font-mono font-bold text-sm">{lamport}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-500 text-xs">Vector</span>
          <span className="text-green-400 font-mono text-xs">{vector}</span>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="bg-slate-900/60 rounded-lg p-2">
          <div className="text-slate-500 mb-0.5">Vuelos</div>
          <div className="text-white font-bold">{flights.toLocaleString()}</div>
        </div>
        <div className="bg-slate-900/60 rounded-lg p-2">
          <div className="text-slate-500 mb-0.5">Delay</div>
          <div className={`font-bold ${delay < 3000 ? 'text-green-400' : delay < 7000 ? 'text-yellow-400' : 'text-red-400'}`}>
            {delay}ms
          </div>
        </div>
        <div className="bg-slate-900/60 rounded-lg p-2">
          <div className="text-slate-500 mb-0.5">Última sync</div>
          <div className="text-white font-mono">{lastSync}</div>
        </div>
        <div className="bg-slate-900/60 rounded-lg p-2">
          <div className="text-slate-500 mb-0.5">Conflictos</div>
          <div className={`font-bold ${conflicts > 0 ? 'text-yellow-400' : 'text-green-400'}`}>
            {conflicts}
          </div>
        </div>
      </div>
    </div>
  )
}

// Animated arrow between nodes
function SyncArrow({ active, label }) {
  return (
    <div className="hidden md:flex flex-col items-center justify-center self-center gap-1 shrink-0">
      <div className={`text-xs font-mono transition-colors ${active ? 'text-blue-400' : 'text-slate-600'}`}>
        {label || 'sync'}
      </div>
      <div className={`flex items-center gap-0 ${active ? 'opacity-100' : 'opacity-30'}`}>
        <div className={`h-px w-8 ${active ? 'bg-blue-400' : 'bg-slate-600'} transition-colors`} />
        <div className={`w-0 h-0 border-y-4 border-y-transparent border-l-6 transition-colors
          ${active ? 'border-l-blue-400' : 'border-l-slate-600'}`}
          style={{ borderLeft: `6px solid ${active ? '#60a5fa' : '#475569'}` }} />
      </div>
    </div>
  )
}

export default function AdminSync() {
  const { nodes, globalStatus, getNodeColor } = useSyncStore()
  const [syncLog, setSyncLog] = useState([])
  const [loading, setLoading] = useState(true)
  const [lastActivity, setLastActivity] = useState(null)
  const [simulatePending, setSimulatePending] = useState(false)
  const [graphStatus, setGraphStatus] = useState(null)
  const [graphLoading, setGraphLoading] = useState(false)
  const logRef = useRef(null)
  const timerRef = useRef(null)

  const loadData = async () => {
    try {
      const log = await getDashboardSyncLog().catch(() => [])
      const entries = Array.isArray(log) ? log : []
      setSyncLog(entries.slice(0, 50))
      if (entries.length > 0) setLastActivity(entries[0])
    } catch {}
    finally { setLoading(false) }
  }

  const loadGraphStatus = async () => {
    setGraphLoading(true)
    const data = await getGraphStatus()
    setGraphStatus(data)
    setGraphLoading(false)
  }

  useEffect(() => {
    loadData()
    loadGraphStatus()
    timerRef.current = setInterval(loadData, 3000)
    return () => clearInterval(timerRef.current)
  }, [])

  // Scroll log to top on update
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = 0
  }, [syncLog.length])

  const simulateConflict = async () => {
    setSimulatePending(true)
    // Add a synthetic conflict entry to demo
    const fake = {
      timestamp: Math.floor(Date.now() / 1000),
      event: 'CONCURRENT_WRITE — Conflict detected: seat_id=42 modified on DB1 and DB2 simultaneously',
      node: 'DB1→DB2',
      vector_clock: '[105,103,98]',
      latency_ms: 12,
      status: 'CONFLICT',
    }
    setSyncLog(prev => [fake, ...prev.slice(0, 49)])
    setTimeout(() => {
      const resolved = {
        timestamp: Math.floor(Date.now() / 1000) + 1,
        event: 'CONFLICT_RESOLVED — Using causal order: DB1 wins (lower node_id). Vector: [106,103,98]',
        node: 'DB1→DB2→DB3',
        vector_clock: '[106,103,98]',
        latency_ms: 8,
        status: 'OK',
      }
      setSyncLog(prev => [resolved, ...prev.slice(0, 49)])
      setSimulatePending(false)
    }, 1500)
  }

  const recentActive = lastActivity &&
    (Math.floor(Date.now() / 1000) - (lastActivity.timestamp || 0)) < 10

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="w-6 h-6 text-purple-400" />
            Panel de Sincronización
          </h1>
          <p className="text-slate-400 text-sm mt-0.5">
            Replicación entre 3 nodos · Lamport + Vector Clocks · AP (Disponibilidad + Particiones)
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={simulateConflict} disabled={simulatePending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-yellow-700 hover:bg-yellow-600
              text-white text-sm font-medium transition-colors disabled:opacity-50">
            <Zap className="w-4 h-4" />
            {simulatePending ? 'Simulando...' : 'Simular conflicto'}
          </button>
          <button onClick={loadData}
            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800 border border-slate-700
              text-slate-400 hover:text-white text-sm transition-colors">
            <RefreshCw className="w-4 h-4" />
            Actualizar
          </button>
        </div>
      </div>

      {/* Global status banner */}
      <div className={`px-4 py-3 rounded-xl border text-sm font-medium flex items-center gap-2
        ${globalStatus === 'aligned'
          ? 'bg-green-900/20 border-green-700 text-green-400'
          : globalStatus === 'conflict'
          ? 'bg-red-900/20 border-red-700 text-red-400'
          : 'bg-yellow-900/20 border-yellow-700 text-yellow-400'}`}>
        {globalStatus === 'aligned'
          ? <><CheckCircle className="w-4 h-4" /> Nodos alineados — Sin conflictos pendientes</>
          : globalStatus === 'conflict'
          ? <><AlertTriangle className="w-4 h-4" /> Conflicto detectado — Resolviendo con Vector Clocks</>
          : <><Clock className="w-4 h-4" /> Propagación pendiente — Consistencia eventual en progreso</>}
      </div>

      {/* 3-column node cards */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr_auto_1fr] gap-4 items-stretch">
        {NODE_CFG.map((cfg, i) => (
          <>
            <NodeCard key={cfg.key} cfg={cfg} nodeData={nodes[cfg.key]} getNodeColor={getNodeColor} />
            {i < NODE_CFG.length - 1 && (
              <SyncArrow key={`arrow-${i}`} active={recentActive} />
            )}
          </>
        ))}
      </div>

      {/* Architecture legend */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div className="text-blue-400 font-semibold mb-2">Algoritmo de Lamport</div>
          <div className="text-slate-400 font-mono">clock = max(local, recibido) + 1</div>
          <div className="text-slate-500 mt-1">Ordena eventos causalmente entre nodos</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div className="text-green-400 font-semibold mb-2">Vector Clock</div>
          <div className="text-slate-400 font-mono">[n1, n2, n3]</div>
          <div className="text-slate-500 mt-1">Detecta causalidad y concurrencia entre operaciones</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div className="text-yellow-400 font-semibold mb-2">Resolución de Conflictos</div>
          <div className="text-slate-400 font-mono">causalidad {'>'} epoch {'>'} node_id</div>
          <div className="text-slate-500 mt-1">Causalidad primero, luego timestamp, luego nodo</div>
        </div>
      </div>

      {/* ─── Rutas disponibles hoy ──────────────────────────────────────────── */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Map className="w-4 h-4 text-blue-400" />
            Rutas disponibles en la BD
            {graphStatus && (
              <span className="text-xs bg-slate-700 px-2 py-0.5 rounded-full text-slate-400 font-normal">
                {graphStatus.date}
              </span>
            )}
          </h3>
          <button
            onClick={loadGraphStatus}
            disabled={graphLoading}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-600
              text-white text-xs font-medium transition-colors disabled:opacity-50"
          >
            <RotateCcw className={`w-3 h-3 ${graphLoading ? 'animate-spin' : ''}`} />
            Recalcular rutas
          </button>
        </div>

        {!graphStatus && !graphLoading && (
          <div className="p-6 text-center text-slate-500 text-sm">
            Haz clic en Recalcular para ver el estado del grafo
          </div>
        )}
        {graphLoading && (
          <div className="p-6 text-center text-slate-500 text-sm">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
            Consultando ms-flights para todas las rutas…
          </div>
        )}

        {graphStatus && !graphLoading && (
          <div className="p-4 space-y-4">
            {/* Stats row */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-slate-900 rounded-xl p-3 text-center">
                <div className="text-2xl font-bold text-blue-400">{graphStatus.real_routes_today}</div>
                <div className="text-xs text-slate-400 mt-0.5">Rutas activas hoy</div>
              </div>
              <div className="bg-slate-900 rounded-xl p-3 text-center">
                <div className="text-2xl font-bold text-yellow-400">{graphStatus.missing_today}</div>
                <div className="text-xs text-slate-400 mt-0.5">Sin vuelo hoy (fallback)</div>
              </div>
              <div className="bg-slate-900 rounded-xl p-3 text-center">
                <div className="text-2xl font-bold text-slate-300">{graphStatus.matrix_routes}</div>
                <div className="text-xs text-slate-400 mt-0.5">Rutas en dataset</div>
              </div>
            </div>

            {/* Available routes table */}
            {graphStatus.available?.length > 0 && (
              <div>
                <div className="text-xs text-green-400 font-semibold mb-2 flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" /> Rutas con vuelos reales hoy
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5 max-h-48 overflow-y-auto">
                  {graphStatus.available.map(r => (
                    <div key={`${r.from}-${r.to}`}
                      className="bg-green-900/20 border border-green-800/40 rounded-lg px-2 py-1.5 text-xs flex items-center justify-between gap-1">
                      <span className="text-white font-mono font-bold">{r.from}→{r.to}</span>
                      <span className="text-green-400">${r.best_price?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Unavailable routes */}
            {graphStatus.unavailable?.length > 0 && (
              <div>
                <div className="text-xs text-yellow-400 font-semibold mb-2 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> Sin vuelo hoy (usan precio de matriz)
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-1.5 max-h-32 overflow-y-auto">
                  {graphStatus.unavailable.map(r => (
                    <div key={`${r.from}-${r.to}`}
                      className="bg-slate-700/30 border border-slate-600/30 rounded-lg px-2 py-1.5 text-xs flex items-center justify-between gap-1">
                      <span className="text-slate-400 font-mono">{r.from}→{r.to}</span>
                      <span className="text-slate-500">${r.matrix_price_economy?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* LiveLogs — microservice HTTP logs */}
      <LiveLogs />

      {/* Event log */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Activity className="w-4 h-4 text-slate-400" />
            Log de eventos en tiempo real
            <span className="text-xs bg-slate-700 px-2 py-0.5 rounded-full text-slate-400 font-normal">
              cada 3s
            </span>
          </h3>
          <span className="text-slate-500 text-xs">{syncLog.length} eventos recientes</span>
        </div>

        <div ref={logRef} className="divide-y divide-slate-700/30 max-h-96 overflow-y-auto">
          {loading && (
            <div className="p-6 text-center text-slate-500 text-sm">
              <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
              Cargando eventos...
            </div>
          )}
          {!loading && syncLog.length === 0 && (
            <div className="p-6 text-center text-slate-500 text-sm">Sin eventos recientes</div>
          )}
          {syncLog.map((ev, i) => {
            const isConflict = ev.status === 'CONFLICT' ||
              (ev.event || '').toLowerCase().includes('conflict')
            return (
              <div key={i}
                className={`px-4 py-3 flex items-start gap-3 text-xs transition-colors
                  hover:bg-slate-700/20 ${isConflict ? 'bg-yellow-900/10' : ''}`}>
                {/* Status dot */}
                <div className={`w-2 h-2 rounded-full mt-0.5 shrink-0
                  ${isConflict ? 'bg-yellow-400' : 'bg-green-400'}`} />

                {/* Timestamp */}
                <span className="text-slate-500 font-mono shrink-0 w-32">
                  {epochToLocal(ev.timestamp)}
                </span>

                {/* Event */}
                <span className={`flex-1 ${isConflict ? 'text-yellow-300' : 'text-slate-300'}`}>
                  {ev.event || ev.message || '—'}
                </span>

                {/* Node */}
                <span className="text-blue-400 font-mono shrink-0">{ev.node || ev.source_node || '—'}</span>

                {/* Vector clock */}
                <span className="text-green-400 font-mono shrink-0 hidden lg:block">
                  {ev.vector_clock || '—'}
                </span>

                {/* Latency */}
                <span className="text-slate-500 font-mono shrink-0">
                  {ev.latency_ms != null ? `${ev.latency_ms}ms` : '—'}
                </span>

                {/* Status badge */}
                <span className={`px-1.5 py-0.5 rounded text-xs shrink-0
                  ${isConflict
                    ? 'bg-yellow-900/40 text-yellow-400'
                    : 'bg-green-900/40 text-green-400'}`}>
                  {isConflict ? '⚠ Conflicto' : '✓ OK'}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
