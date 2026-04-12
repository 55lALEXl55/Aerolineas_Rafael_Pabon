import { useState } from 'react'
import { STATUS_COLORS } from '../../utils/seatLayout'
import { SeatLegend } from './A380SeatMap'

// B787-9: 228 asientos
// Primera clase: fila 1, 2-2-2-2 (AB | CD | EF | GH)
// Turista: filas 3-30, 3-3-2 (ABC | DEF | GH)

function Seat({ seatNum, seat, onClick, small = false }) {
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
        className={`${small ? 'w-6 h-6 text-[7px]' : 'w-7 h-7 text-[8px]'} rounded-sm flex items-center justify-center
          font-bold text-white ${canClick ? 'cursor-pointer hover:brightness-125' : 'cursor-default'} transition-all`}
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

function Aisle() { return <div className="w-4 shrink-0" /> }

export default function B787SeatMap({ seatMap, onSeatClick }) {
  const firstRows = [1]
  const ecoRows = Array.from({ length: 28 }, (_, i) => i + 3)

  return (
    <div className="flex flex-col items-center gap-1 py-4 select-none">
      <div className="text-slate-500 text-xs mb-2">▲ Cabina</div>

      <div className="text-xs text-amber-400 font-semibold mb-1 self-start ml-12">PRIMERA CLASE</div>
      <div className="flex flex-col gap-0.5">
        {firstRows.map(row => (
          <div key={row} className="flex items-center gap-0.5">
            <span className="w-8 text-right text-xs text-slate-500 mr-1">{row}</span>
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
            <Aisle />
            {['G','H'].map(col => (
              <Seat key={col} seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
          </div>
        ))}
      </div>

      <div className="w-full border-t border-dashed border-slate-600 my-3" />

      <div className="text-xs text-blue-400 font-semibold mb-1 self-start ml-12">TURISTA</div>
      <div className="flex items-center gap-0.5 mb-0.5">
        <span className="w-9" />
        {['A','B','C'].map(c => <span key={c} className="w-6 text-center text-xs text-slate-500">{c}</span>)}
        <Aisle />
        {['D','E','F'].map(c => <span key={c} className="w-6 text-center text-xs text-slate-500">{c}</span>)}
        <Aisle />
        {['G','H'].map(c => <span key={c} className="w-6 text-center text-xs text-slate-500">{c}</span>)}
      </div>

      <div className="flex flex-col gap-0.5 max-h-[580px] overflow-y-auto pr-1">
        {ecoRows.map(row => (
          <div key={row} className="flex items-center gap-0.5">
            <span className="w-8 text-right text-xs text-slate-500 mr-1">{row}</span>
            {['A','B','C'].map(col => (
              <Seat key={col} small seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
            <Aisle />
            {['D','E','F'].map(col => (
              <Seat key={col} small seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
            <Aisle />
            {['G','H'].map(col => (
              <Seat key={col} small seatNum={`${row}${col}`} seat={seatMap[`${row}${col}`]} onClick={onSeatClick} />
            ))}
          </div>
        ))}
      </div>
      <SeatLegend />
    </div>
  )
}
