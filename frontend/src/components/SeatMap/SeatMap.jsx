import { getAircraftModel, STATUS_COLORS } from '../../utils/seatLayout'
import A380SeatMap from './A380SeatMap'
import B777SeatMap from './B777SeatMap'
import A350SeatMap from './A350SeatMap'
import B787SeatMap from './B787SeatMap'

const MAP_COMPONENTS = {
  'A380-800':   A380SeatMap,
  'B777-300ER': B777SeatMap,
  'A350-900':   A350SeatMap,
  'B787-9':     B787SeatMap,
}

export default function SeatMap({ aircraftId, seats = [], onSeatClick }) {
  const model = getAircraftModel(aircraftId)
  const Component = MAP_COMPONENTS[model] || B777SeatMap

  // Build seat status map keyed by "rowcol" e.g. "1A"
  const seatMap = {}
  seats.forEach(s => {
    seatMap[s.seat_number] = s
  })

  return (
    <div className="w-full overflow-x-auto">
      <Component seatMap={seatMap} onSeatClick={onSeatClick} />
    </div>
  )
}
