import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Plane, Users, DollarSign } from 'lucide-react'
import { getFlightById, getFlightSeats, lockSeat, generateToken } from '../api'
import { epochToLocal, epochToTime, durationStr } from '../utils/epochUtils'
import { getAircraftModel } from '../utils/seatLayout'
import { getAirportTz } from '../utils/geoRouter'
import SeatMap from '../components/SeatMap/SeatMap'
import BookingModal from '../components/BookingModal'
import AircraftCard from '../components/AircraftCard'
import { useBookingStore } from '../stores/bookingStore'

export default function SeatSelection() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { selectedFlight: storeFlight, setSelectedFlight, setSessionToken } = useBookingStore()

  const [flight, setFlight] = useState(storeFlight)
  const [seats, setSeats] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedSeat, setSelectedSeat] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)

  useEffect(() => {
    loadData()
    const interval = setInterval(loadSeats, 5000)
    return () => clearInterval(interval)
  }, [id])

  async function loadData() {
    setLoading(true)
    try {
      const [f, s] = await Promise.all([
        storeFlight?.flight_id === parseInt(id) ? storeFlight : getFlightById(id),
        getFlightSeats(id),
      ])
      setFlight(f)
      setSelectedFlight(f)
      setSeats(Array.isArray(s) ? s : s.seats || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  async function loadSeats() {
    try {
      const s = await getFlightSeats(id)
      setSeats(Array.isArray(s) ? s : s.seats || [])
    } catch { /* ignore */ }
  }

  const handleSeatClick = async (seat) => {
    setSelectedSeat(seat)
    // Auto-lock if available
    if (seat.status === 'AVAILABLE') {
      try {
        const token = generateToken()
        setSessionToken(token)
        await lockSeat(flight.flight_id, seat.seat_id, token)
      } catch { /* seat may already be locked */ }
    }
    setModalOpen(true)
  }

  const handleModalConfirm = () => {
    setModalOpen(false)
    loadSeats()
  }

  // Stats
  const stats = seats.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] || 0) + 1
    return acc
  }, {})

  const revenue = {
    first: seats.filter(s => s.seat_class === 'FIRST' && s.status === 'SOLD').reduce((a, s) => a + s.price, 0),
    economy: seats.filter(s => s.seat_class === 'ECONOMY' && s.status === 'SOLD').reduce((a, s) => a + s.price, 0),
  }

  const model = flight ? getAircraftModel(flight.aircraft_id) : 'B777-300ER'

  if (loading && !flight) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">{t('common.loading')}</div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Back */}
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm">
        <ArrowLeft className="w-4 h-4" /> Volver
      </button>

      {/* Flight info */}
      {flight && (
        <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{flight.origin}</div>
                <div className="text-slate-400 text-sm">{epochToTime(flight.departure_epoch, getAirportTz(flight.origin))}</div>
              </div>
              <div className="flex flex-col items-center">
                <div className="text-xs text-slate-500">{durationStr(flight.duration_minutes, t)}</div>
                <div className="flex items-center gap-2 my-1">
                  <div className="h-px w-12 bg-slate-600" />
                  <Plane className="w-4 h-4 text-blue-400" />
                  <div className="h-px w-12 bg-slate-600" />
                </div>
                <div className="text-xs text-green-400">Directo</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{flight.destination}</div>
                <div className="text-slate-400 text-sm">{epochToTime(flight.arrival_epoch, getAirportTz(flight.destination))}</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-blue-400">${flight.price_economy}</div>
              <div className="text-slate-400 text-sm">{flight.flight_number}</div>
              <div className="text-slate-500 text-xs">{model}</div>
            </div>
          </div>
        </div>
      )}

      {/* Aircraft spec card */}
      {flight && <AircraftCard model={model} aircraftId={flight.aircraft_id} />}

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { key: 'AVAILABLE', label: t('seat.available'), color: 'text-blue-400', bg: 'bg-blue-900/20 border-blue-800' },
          { key: 'RESERVED',  label: t('seat.reserved'),  color: 'text-amber-400', bg: 'bg-amber-900/20 border-amber-800' },
          { key: 'SOLD',      label: t('seat.sold'),      color: 'text-green-400', bg: 'bg-green-900/20 border-green-800' },
          { key: 'LOCKED',    label: t('seat.locked'),    color: 'text-gray-400',  bg: 'bg-gray-900/20 border-gray-700' },
          { key: 'REFUNDED',  label: t('seat.refunded'),  color: 'text-red-400',   bg: 'bg-red-900/20 border-red-800' },
        ].map(({ key, label, color, bg }) => (
          <div key={key} className={`border rounded-xl p-3 text-center ${bg}`}>
            <div className={`text-2xl font-bold ${color}`}>{stats[key] || 0}</div>
            <div className="text-xs text-slate-400 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Revenue */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
          <div className="text-slate-400 text-xs mb-1 flex items-center justify-center gap-1">
            <DollarSign className="w-3 h-3" /> Primera
          </div>
          <div className="text-amber-400 font-bold text-xl">${revenue.first.toLocaleString()}</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
          <div className="text-slate-400 text-xs mb-1 flex items-center justify-center gap-1">
            <DollarSign className="w-3 h-3" /> Turista
          </div>
          <div className="text-blue-400 font-bold text-xl">${revenue.economy.toLocaleString()}</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
          <div className="text-slate-400 text-xs mb-1 flex items-center justify-center gap-1">
            <Users className="w-3 h-3" /> Total
          </div>
          <div className="text-white font-bold text-xl">${(revenue.first + revenue.economy).toLocaleString()}</div>
        </div>
      </div>

      {/* Seat map */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-slate-700">
          <h3 className="text-white font-semibold">Mapa de asientos · {model}</h3>
          <p className="text-slate-400 text-xs mt-0.5">Haz clic en un asiento azul o amarillo para continuar</p>
        </div>
        {loading ? (
          <div className="h-32 flex items-center justify-center text-slate-500">{t('common.loading')}</div>
        ) : (
          <SeatMap aircraftId={flight?.aircraft_id} seats={seats} onSeatClick={handleSeatClick} />
        )}
      </div>

      {/* Booking modal */}
      {modalOpen && selectedSeat && (
        <BookingModal
          seat={selectedSeat}
          flight={flight}
          onClose={() => setModalOpen(false)}
          onConfirm={handleModalConfirm}
        />
      )}
    </div>
  )
}
