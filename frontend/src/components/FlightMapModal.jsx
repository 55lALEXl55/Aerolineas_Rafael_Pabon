import { useEffect, useRef, useState } from 'react'
import { X, Clock, DollarSign, Plane } from 'lucide-react'
import { getAirportSvgPos, getAirportFlag, getAirportName } from '../utils/geoRouter'
import { durationStr } from '../utils/epochUtils'
import { getAircraftModel } from '../utils/seatLayout'
import { useTranslation } from 'react-i18next'

// ─── SVG world map continent paths (viewBox 0 0 100 72) ──────────────────────
const CONTINENTS = [
  // North America
  { d: 'M 4,6 L 14,5 L 28,6 L 32,11 L 30,18 L 27,26 L 24,32 L 20,39 L 17,43 L 14,47 L 11,46 L 8,40 L 5,32 L 4,20 Z', fill: '#1e3a5f' },
  // South America
  { d: 'M 20,50 L 32,47 L 37,52 L 36,59 L 32,66 L 27,68 L 22,65 L 19,58 Z', fill: '#1e3a5f' },
  // Europe
  { d: 'M 43,13 L 56,11 L 60,15 L 59,22 L 54,28 L 47,29 L 43,25 Z', fill: '#1e4a3f' },
  // Africa
  { d: 'M 43,29 L 58,27 L 63,33 L 61,45 L 55,52 L 47,52 L 41,45 L 40,36 Z', fill: '#1e4a3f' },
  // Middle East
  { d: 'M 58,26 L 70,24 L 72,30 L 68,36 L 62,37 L 57,32 Z', fill: '#2a3a4a' },
  // Asia (large)
  { d: 'M 60,9 L 75,8 L 86,9 L 92,14 L 94,22 L 90,30 L 86,34 L 80,36 L 74,34 L 68,28 L 64,22 L 60,18 Z', fill: '#1a3a5a' },
  // Southeast Asia + Indonesia
  { d: 'M 72,34 L 82,34 L 85,40 L 82,46 L 78,48 L 73,46 L 71,40 Z', fill: '#1a3a5a' },
  // Australia
  { d: 'M 79,53 L 90,51 L 93,56 L 90,63 L 83,65 L 78,62 L 78,56 Z', fill: '#1a3a3a' },
  // Greenland
  { d: 'M 28,3 L 38,2 L 41,7 L 36,10 L 28,9 Z', fill: '#1e3a5f' },
]

const NODE_COLORS = { 1: '#3b82f6', 2: '#a855f7', 3: '#f97316' }

// Compute quadratic bezier arc between two SVG points
function arcPath(p1, p2, lift = 0.35) {
  const mx = (p1.x + p2.x) / 2
  const my = (p1.y + p2.y) / 2
  // Control point: midpoint pushed upward proportional to distance
  const dx = p2.x - p1.x
  const dy = p2.y - p1.y
  const dist = Math.sqrt(dx * dx + dy * dy)
  const cy = my - dist * lift
  return `M ${p1.x},${p1.y} Q ${mx},${cy} ${p2.x},${p2.y}`
}

// Build composite path through all waypoints
function buildFlightPath(stops) {
  if (stops.length < 2) return ''
  let path = ''
  for (let i = 0; i < stops.length - 1; i++) {
    const p1 = getAirportSvgPos(stops[i])
    const p2 = getAirportSvgPos(stops[i + 1])
    if (i === 0) {
      path += arcPath(p1, p2)
    } else {
      const mx = (p1.x + p2.x) / 2
      const my = (p1.y + p2.y) / 2
      const dx = p2.x - p1.x, dy = p2.y - p1.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      const cy = my - dist * 0.35
      path += ` Q ${mx},${cy} ${p2.x},${p2.y}`
    }
  }
  return path
}

export default function FlightMapModal({ route, onClose, onSelect }) {
  const { t } = useTranslation()
  const pathRef = useRef(null)
  const planeRef = useRef(null)
  const [animDone, setAnimDone] = useState(false)
  const [pathLen, setPathLen] = useState(0)

  const flights = route?.flights || (route ? [route] : [])
  const firstFlight = flights[0]
  const lastFlight = flights[flights.length - 1]

  // Build stops array: all airports in the route
  const stops = []
  if (firstFlight?.origin) stops.push(firstFlight.origin)
  for (const f of flights) {
    if (f.destination && !stops.includes(f.destination)) stops.push(f.destination)
  }

  const flightPath = buildFlightPath(stops)
  const totalPrice = route?.total_cost ?? firstFlight?.price_economy ?? 0
  const totalMins  = route?.total_minutes ?? flights.reduce((s, f) => s + (f.duration_minutes || 0), 0)
  const model = firstFlight ? getAircraftModel(firstFlight.aircraft_id) : ''

  // Measure path length for dash animation
  useEffect(() => {
    if (pathRef.current) {
      const len = pathRef.current.getTotalLength()
      setPathLen(len)
    }
  }, [flightPath])

  // Start animation once pathLen is set
  useEffect(() => {
    if (!pathLen || !pathRef.current) return
    pathRef.current.style.strokeDasharray = `${pathLen}`
    pathRef.current.style.strokeDashoffset = `${pathLen}`
    pathRef.current.style.transition = 'none'
    // Force reflow
    void pathRef.current.getBoundingClientRect()
    pathRef.current.style.transition = `stroke-dashoffset 2.4s cubic-bezier(0.4,0,0.2,1)`
    pathRef.current.style.strokeDashoffset = '0'
    const timer = setTimeout(() => setAnimDone(true), 2600)
    return () => clearTimeout(timer)
  }, [pathLen])

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4"
         onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl shadow-2xl
                      animate-[fadeSlideUp_0.25s_ease-out]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <Plane className="w-5 h-5 text-blue-400" />
            <span className="text-white font-semibold text-lg">
              {firstFlight?.origin} → {lastFlight?.destination}
            </span>
            {stops.length > 2 && (
              <span className="text-amber-400 text-sm bg-amber-900/30 px-2 py-0.5 rounded">
                {stops.length - 2} escala{stops.length - 2 > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* SVG World Map */}
        <div className="relative bg-slate-950 mx-4 mt-4 rounded-xl overflow-hidden border border-slate-800">
          <svg
            viewBox="0 0 100 72"
            className="w-full"
            style={{ height: '280px' }}
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Ocean background */}
            <rect width="100" height="72" fill="#0a1628" />

            {/* Grid lines */}
            {[15, 30, 45, 60].map(y => (
              <line key={y} x1="0" y1={y} x2="100" y2={y} stroke="#ffffff08" strokeWidth="0.2" />
            ))}
            {[20, 40, 60, 80].map(x => (
              <line key={x} x1={x} y1="0" x2={x} y2="72" stroke="#ffffff08" strokeWidth="0.2" />
            ))}

            {/* Continents */}
            {CONTINENTS.map((c, i) => (
              <path key={i} d={c.d} fill={c.fill} stroke="#ffffff18" strokeWidth="0.3" />
            ))}

            {/* Flight path (animated) */}
            {flightPath && (
              <path
                ref={pathRef}
                d={flightPath}
                fill="none"
                stroke="#60a5fa"
                strokeWidth="0.6"
                strokeDasharray="1.2,0.8"
                opacity="0.9"
              />
            )}

            {/* Glow effect on path when done */}
            {animDone && flightPath && (
              <path
                d={flightPath}
                fill="none"
                stroke="#93c5fd"
                strokeWidth="0.3"
                opacity="0.5"
              />
            )}

            {/* All airports (dimmed) */}
            {Object.entries({
              ATL:{x:18,y:38,n:1}, LAX:{x:10,y:37,n:1}, DFW:{x:15,y:40,n:1}, SAO:{x:30,y:65,n:1},
              LON:{x:47,y:25,n:2}, PAR:{x:48,y:27,n:2}, FRA:{x:50,y:26,n:2}, MAD:{x:45,y:30,n:2},
              AMS:{x:49,y:24,n:2}, IST:{x:56,y:30,n:2}, DXB:{x:62,y:38,n:2},
              PEK:{x:78,y:30,n:3}, TYO:{x:83,y:32,n:3}, SIN:{x:76,y:48,n:3}, CAN:{x:78,y:38,n:3},
            }).map(([code, pos]) => {
              const isStop = stops.includes(code)
              return (
                <g key={code}>
                  <circle
                    cx={pos.x} cy={pos.y} r={isStop ? 1.2 : 0.6}
                    fill={isStop ? NODE_COLORS[pos.n] : NODE_COLORS[pos.n] + '55'}
                    stroke={isStop ? 'white' : 'none'}
                    strokeWidth="0.3"
                  />
                  {isStop && (
                    <text x={pos.x + 1.5} y={pos.y + 0.8} fontSize="2.2" fill="white" fontWeight="bold">
                      {code}
                    </text>
                  )}
                </g>
              )
            })}

            {/* Animated plane icon */}
            {flightPath && (
              <g ref={planeRef}>
                <animateMotion
                  dur="2.4s"
                  begin="0.1s"
                  path={flightPath}
                  rotate="auto"
                  fill="freeze"
                />
                <text fontSize="3.5" textAnchor="middle" dominantBaseline="middle" y="-0.3">✈</text>
              </g>
            )}

            {/* Stopover markers */}
            {stops.slice(1, -1).map(code => {
              const pos = getAirportSvgPos(code)
              return (
                <g key={`stop-${code}`}>
                  <circle cx={pos.x} cy={pos.y} r="2" fill="none"
                    stroke="#fbbf24" strokeWidth="0.5" strokeDasharray="1,0.5"
                    opacity={animDone ? 1 : 0}
                    style={{ transition: 'opacity 0.5s' }}
                  />
                  <text x={pos.x} y={pos.y + 3.5} fontSize="2" fill="#fbbf24"
                    textAnchor="middle" opacity={animDone ? 1 : 0}
                    style={{ transition: 'opacity 0.5s' }}>
                    ESCALA
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Flight details */}
        <div className="p-4">
          {/* Route legs */}
          <div className="flex items-center gap-2 flex-wrap mb-4">
            {stops.map((code, i) => (
              <div key={code} className="flex items-center gap-2">
                <div className="text-center">
                  <div className="text-white font-bold text-lg">{code}</div>
                  <div className="text-slate-400 text-xs">{getAirportFlag(code)} {getAirportName(code)}</div>
                </div>
                {i < stops.length - 1 && (
                  <div className="flex flex-col items-center">
                    <div className="text-slate-500 text-xs">{durationStr(flights[i]?.duration_minutes, t)}</div>
                    <div className="text-slate-500 text-lg">→</div>
                    {stops.length > 2 && i < stops.length - 2 && (
                      <div className="text-amber-400 text-xs">escala</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-slate-800 rounded-xl p-3 text-center border border-slate-700">
              <div className="text-slate-400 text-xs flex items-center justify-center gap-1 mb-1">
                <DollarSign className="w-3 h-3" /> Precio
              </div>
              <div className="text-blue-400 font-bold text-xl">${totalPrice.toLocaleString()}</div>
            </div>
            <div className="bg-slate-800 rounded-xl p-3 text-center border border-slate-700">
              <div className="text-slate-400 text-xs flex items-center justify-center gap-1 mb-1">
                <Clock className="w-3 h-3" /> Duración
              </div>
              <div className="text-white font-bold text-lg">{durationStr(totalMins, t)}</div>
            </div>
            <div className="bg-slate-800 rounded-xl p-3 text-center border border-slate-700">
              <div className="text-slate-400 text-xs mb-1">Avión</div>
              <div className="text-white font-semibold text-sm">{model}</div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 py-2.5 rounded-xl bg-slate-700 hover:bg-slate-600 text-slate-300 font-medium transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={() => onSelect(route)}
              className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold
                         transition-all hover:scale-[1.02] flex items-center justify-center gap-2"
            >
              <Plane className="w-4 h-4" />
              Seleccionar este vuelo →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
