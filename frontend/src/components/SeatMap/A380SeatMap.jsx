import { useState } from 'react'
import { STATUS_COLORS } from '../../utils/seatLayout'

// A380-800: 449 asientos
// Primera clase: filas 1-2, configuración 2-2-2 (AB | CD | EF)
// Turista: filas 5-29, configuración 3-4-3 (ABC | DEFG | HJK)

const FIRST_COLS = ['A','B','C','D','E','F','G','H','J','K']  // 10 cols primera (2 filas)
const ECO_COLS   = ['A','B','C','D','E','F','G','H','J','K']  // 10 cols turista

function Seat({ seatNum, seat, onClick }) {
  const [hovered, setHovered] = useState(false)
  const status = seat?.status || 'AVAILABLE'
  const color = STATUS_COLORS[status] || STATUS_COLORS.AVAILABLE
  const canClick = status === 'AVAILABLE' || status === 'RESERVED'

  return (
    <div className="relative">
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => canClick && onClick?.(seat || { seat_number: seatNum, status: 'AVAILABLE' })}
        style={{ backgroundColor: color, opacity: status === 'SOLD' ? 0.7 : 1 }}
        className={`w-7 h-7 rounded-sm flex items-center justify-center text-[8px] font-bold text-white
          ${canClick ? 'cursor-pointer hover:brightness-125' : 'cursor-default'} transition-all`}
        title={seatNum}
      >
        {seatNum}
      </div>
      {hovered && seat && (status === 'SOLD' || status === 'RESERVED') && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 bg-slate-900 border border-slate-600
          text-white text-xs rounded px-2 py-1 whitespace-nowrap z-50 pointer-events-none shadow-lg">
          <div className="font-medium">{seat.passenger_name || '—'}</div>
          <div className="text-slate-400">{seat.status}</div>
        </div>
      )}
    </div>
  )
}

function Aisle({ width = 'w-4' }) {
  return <div className={`${width} shrink-0`} />
}

export default function A380SeatMap({ seatMap, onSeatClick }) {
  // Primera clase: filas 1-2 (5 pares de asientos = 10 por fila... usamos 2 filas x 5 = 10 total)
  const firstRows = [1, 2]
  const ecoRows = Array.from({ length: 29 - 4 }, (_, i) => i + 5)  // 5 a 29 = 25 filas x 10 cols ≈ 250... ajustar

  return (
    <div className="flex flex-col items-center gap-1 py-4 select-none">
      {/* Nose indicator */}
      <div className="text-slate-500 text-xs mb-2">▲ Cabina</div>

      {/* ── Primera clase ─────────────────────────────── */}
      <div className="text-xs text-amber-400 font-semibold mb-1 self-start ml-12">PRIMERA CLASE</div>
      <div className="flex flex-col gap-0.5">
        {firstRows.map(row => (
          <div key={row} className="flex items-center gap-0.5">
            <span className="w-8 text-right text-xs text-slate-500 mr-1">{row}</span>
            {/* 2-2-2 first class layout */}
            {['A','B'].map(col => (
              <Seat key={col} seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
            <Aisle />
            {['C','D'].map(col => (
              <Seat key={col} seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
            <Aisle />
            {['E','F'].map(col => (
              <Seat key={col} seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
          </div>
        ))}
      </div>

      <div className="w-full border-t border-dashed border-slate-600 my-3" />

      {/* ── Turista ──────────────────────────────────── */}
      <div className="text-xs text-blue-400 font-semibold mb-1 self-start ml-12">TURISTA</div>

      {/* Column headers */}
      <div className="flex items-center gap-0.5 mb-0.5">
        <span className="w-9" />
        {['A','B','C'].map(c => <span key={c} className="w-7 text-center text-xs text-slate-500">{c}</span>)}
        <Aisle />
        {['D','E','F','G'].map(c => <span key={c} className="w-7 text-center text-xs text-slate-500">{c}</span>)}
        <Aisle />
        {['H','J','K'].map(c => <span key={c} className="w-7 text-center text-xs text-slate-500">{c}</span>)}
      </div>

      <div className="flex flex-col gap-0.5 max-h-[600px] overflow-y-auto pr-1">
        {ecoRows.map(row => (
          <div key={row} className="flex items-center gap-0.5">
            <span className="w-8 text-right text-xs text-slate-500 mr-1">{row}</span>
            {/* 3-4-3 economy layout */}
            {['A','B','C'].map(col => (
              <Seat key={col} seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
            <Aisle />
            {['D','E','F','G'].map(col => (
              <Seat key={col} seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
            <Aisle />
            {['H','J','K'].map(col => (
              <Seat key={col} seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
          </div>
        ))}
      </div>

      {/* Legend */}
      <SeatLegend />
    </div>
  )
}

export function SeatLegend() {
  const items = [
    { status: 'AVAILABLE', color: STATUS_COLORS.AVAILABLE, label: 'Disponible' },
    { status: 'RESERVED',  color: STATUS_COLORS.RESERVED,  label: 'Reservado' },
    { status: 'SOLD',      color: STATUS_COLORS.SOLD,      label: 'Vendido' },
    { status: 'LOCKED',    color: STATUS_COLORS.LOCKED,    label: 'Bloqueado' },
    { status: 'REFUNDED',  color: STATUS_COLORS.REFUNDED,  label: 'Devuelto' },
  ]
  return (
    <div className="flex flex-wrap justify-center gap-3 mt-4 pt-3 border-t border-slate-700">
      {items.map(({ color, label }) => (
        <div key={label} className="flex items-center gap-1.5 text-xs text-slate-300">
          <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: color }} />
          {label}
        </div>
      ))}
    </div>
  )
}
