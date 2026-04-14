import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Plane, Users, DollarSign, ShoppingCart, X, CheckCircle, Loader2, CreditCard } from 'lucide-react'
import { getFlightById, getFlightSeats, lockSeat, generateToken, purchaseMultiple, buySeat, getPassengerByPassport, searchPassengersByPrefix } from '../api'
import { epochToLocal, epochToTime, durationStr } from '../utils/epochUtils'
import { getAircraftModel } from '../utils/seatLayout'
import { getAirportTz } from '../utils/geoRouter'
import SeatMap from '../components/SeatMap/SeatMap'
import BookingModal from '../components/BookingModal'
import AircraftCard from '../components/AircraftCard'
import { useBookingStore } from '../stores/bookingStore'

const getDisplayPrice = (flight, seatClass) => {
  if (seatClass === 'FIRST') {
    return flight.price_first || flight.first_class_price || flight.price_economy || 0
  }
  return flight.price_economy || flight.economy_price || 0
}

export default function SeatSelection() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  // Contexto de ruta con escala
  const isConnecting = location.state?.isConnecting || false
  const allLegs = location.state?.allLegs || []
  const {
    selectedFlight: storeFlight, setSelectedFlight, setSessionToken, sessionToken,
    selectedClass, selectedSeats, addSeat, removeSeat, clearSeats,
  } = useBookingStore()

  const [flight, setFlight] = useState(storeFlight)
  const [seats, setSeats] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedSeat, setSelectedSeat] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [multiMode, setMultiMode] = useState(false)
  const [multiModal, setMultiModal] = useState(false)
  const [multiSuccess, setMultiSuccess] = useState(null)  // result from purchase-multiple
  const BASE = import.meta.env.VITE_API_URL || ''

  // ── Connecting flight state ────────────────────────────────────────────────
  const [currentLegIndex, setCurrentLegIndex] = useState(0)
  const [selectedSeatsPerLeg, setSelectedSeatsPerLeg] = useState({})
  const [connectingModal, setConnectingModal] = useState(false)
  // Track which flight's seats to show (changes when we advance to leg 2)
  const [currentFlightId, setCurrentFlightId] = useState(parseInt(id))

  useEffect(() => {
    const fid = currentFlightId
    loadData(fid)
    const interval = setInterval(() => loadSeats(fid), 5000)
    return () => clearInterval(interval)
  }, [currentFlightId])

  // Clear cart when leaving the page
  useEffect(() => () => clearSeats(), [])

  async function loadData(fid) {
    const flightId = fid || parseInt(id)
    setLoading(true)
    try {
      const [f, s] = await Promise.all([
        storeFlight?.flight_id === flightId ? storeFlight : getFlightById(flightId),
        getFlightSeats(flightId),
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

  async function loadSeats(fid) {
    const flightId = fid || parseInt(id)
    try {
      const s = await getFlightSeats(flightId)
      setSeats(Array.isArray(s) ? s : s.seats || [])
    } catch { /* ignore */ }
  }

  const handleSeatClick = async (seat) => {
    // ── Connecting mode: 2-step seat selection ─────────────────────────────
    if (isConnecting && seat.status === 'AVAILABLE') {
      try {
        const token = sessionToken || generateToken()
        setSessionToken(token)
        await lockSeat(currentFlightId, seat.seat_id, token)
        const currentLeg = allLegs[currentLegIndex]
        setSelectedSeatsPerLeg(prev => ({
          ...prev,
          [currentLegIndex]: { ...seat, flightId: currentFlightId, leg: currentLeg },
        }))
        if (currentLegIndex < allLegs.length - 1) {
          const nextIdx = currentLegIndex + 1
          setCurrentLegIndex(nextIdx)
          setCurrentFlightId(allLegs[nextIdx].flight_id)
        } else {
          setConnectingModal(true)
        }
      } catch { /* seat may already be locked */ }
      return
    }

    if (multiMode && seat.status === 'AVAILABLE') {
      // Guardia: seat_id es requerido por /bookings/lock
      if (!seat.seat_id) {
        console.warn('[SeatSelection] seat sin seat_id en modo multi:', seat)
        return
      }
      // Multi-select mode: lock + add to cart, no modal
      const alreadySelected = selectedSeats.some(s => s.seat_id === seat.seat_id)
      if (alreadySelected) {
        removeSeat(seat.seat_id)
        return
      }
      try {
        const token = sessionToken || generateToken()
        setSessionToken(token)
        await lockSeat(flight.flight_id, seat.seat_id, token)
        addSeat({ ...seat, status: 'LOCKED' })
        loadSeats(currentFlightId)
      } catch { /* seat may already be locked */ }
      return
    }

    // Single-seat mode (existing behavior)
    setSelectedSeat(seat)
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
    loadSeats(currentFlightId)
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
      <div className="max-w-5xl mx-auto space-y-4 animate-pulse">
        <div className="h-10 w-24 bg-slate-800 rounded-lg" />
        <div className="h-32 bg-slate-800 rounded-2xl" />
        <div className="grid grid-cols-5 gap-3">
          {[0,1,2,3,4].map(i => <div key={i} className="h-20 bg-slate-800 rounded-xl" />)}
        </div>
        <div className="h-96 bg-slate-800 rounded-2xl" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      {/* Back */}
      <button onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm">
        <ArrowLeft className="w-4 h-4" /> {t('nav.back')}
      </button>

      {/* Banner de ruta con escala — progreso por tramos */}
      {isConnecting && allLegs.length > 0 && (
        <div className="bg-blue-900/30 border border-blue-700/50 rounded-xl px-4 py-3 space-y-2">
          <div className="flex items-center gap-3">
            <Plane className="w-4 h-4 text-blue-400 shrink-0" />
            <div className="text-sm flex-1">
              <span className="text-blue-300 font-semibold">
                Tramo {currentLegIndex + 1} de {allLegs.length}:
              </span>
              <span className="text-white font-bold ml-2">
                {allLegs[currentLegIndex]?.origin} → {allLegs[currentLegIndex]?.destination}
              </span>
              <span className="text-blue-400 ml-2 text-xs">
                · Elige tu asiento y haz clic para continuar
              </span>
            </div>
            <div className="flex gap-1.5 shrink-0">
              {allLegs.map((_, i) => (
                <div key={i} className={`w-2.5 h-2.5 rounded-full transition-colors ${
                  i < currentLegIndex ? 'bg-green-400' :
                  i === currentLegIndex ? 'bg-blue-400 animate-pulse' :
                  'bg-slate-600'
                }`} />
              ))}
            </div>
          </div>
          {/* Asientos ya elegidos */}
          {Object.entries(selectedSeatsPerLeg).map(([legIdx, s]) => (
            <div key={legIdx} className="flex items-center gap-2 text-xs text-green-300 bg-green-900/20 rounded-lg px-3 py-1.5">
              <span className="text-green-400">✓</span>
              <span>Tramo {parseInt(legIdx) + 1} ({allLegs[parseInt(legIdx)]?.origin} → {allLegs[parseInt(legIdx)]?.destination}):</span>
              <span className="font-mono font-bold">{s.seat_number}</span>
              <span className="text-green-400 ml-auto">${s.price?.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Flight info */}
      {flight && (
        <div className="bg-slate-800 border border-slate-700 rounded-2xl p-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-6">
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{flight.origin}</div>
                <div className="text-slate-400 text-sm">
                  {epochToTime(flight.departure_epoch, getAirportTz(flight.origin))}
                  <span className="text-slate-500 text-xs ml-1">{flight.origin}</span>
                </div>
              </div>
              <div className="flex flex-col items-center">
                <div className="text-xs text-slate-500">{durationStr(flight.duration_minutes, t)}</div>
                <div className="flex items-center gap-2 my-1">
                  <div className="h-px w-12 bg-slate-600" />
                  <Plane className="w-4 h-4 text-blue-400" />
                  <div className="h-px w-12 bg-slate-600" />
                </div>
                <div className="text-xs text-green-400">{t('flight.direct')}</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-white">{flight.destination}</div>
                <div className="text-slate-400 text-sm">
                  {epochToTime(
                    flight.arrival_epoch || (flight.departure_epoch + (flight.duration_minutes || 0) * 60),
                    getAirportTz(flight.destination)
                  )}
                  <span className="text-slate-500 text-xs ml-1">{flight.destination}</span>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-blue-400">
                ${getDisplayPrice(flight, selectedClass || 'ECONOMY').toLocaleString()}
              </div>
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
            <DollarSign className="w-3 h-3" /> {t('seat.first')}
          </div>
          <div className="text-amber-400 font-bold text-xl">${revenue.first.toLocaleString()}</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
          <div className="text-slate-400 text-xs mb-1 flex items-center justify-center gap-1">
            <DollarSign className="w-3 h-3" /> {t('seat.economy')}
          </div>
          <div className="text-blue-400 font-bold text-xl">${revenue.economy.toLocaleString()}</div>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
          <div className="text-slate-400 text-xs mb-1 flex items-center justify-center gap-1">
            <Users className="w-3 h-3" /> {t('seat.total')}
          </div>
          <div className="text-white font-bold text-xl">${(revenue.first + revenue.economy).toLocaleString()}</div>
        </div>
      </div>

      {/* Seat map */}
      <div className="bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-slate-700 flex items-center justify-between">
          <div>
            <h3 className="text-white font-semibold">{t('seat.map_title')} · {model}</h3>
            <p className="text-slate-400 text-xs mt-0.5">{t('seat.map_hint')}</p>
          </div>
          {!isConnecting && (
            <button
              onClick={() => { setMultiMode(m => !m); if (multiMode) clearSeats() }}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors
                ${multiMode ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}
            >
              <ShoppingCart className="w-4 h-4" />
              {multiMode ? t('seat.multi_on') : t('seat.multi_off')}
            </button>
          )}
        </div>
        {multiMode && (
          <div className="px-4 py-2 bg-blue-900/20 border-b border-blue-800/40 text-blue-300 text-xs">
            {t('seat.multi_hint')}
          </div>
        )}
        {loading ? (
          <div className="h-32 flex items-center justify-center text-slate-500">{t('common.loading')}</div>
        ) : (
          <SeatMap aircraftId={flight?.aircraft_id} seats={seats} onSeatClick={handleSeatClick} />
        )}
      </div>

      {/* Multi-seat cart panel */}
      {selectedSeats.length > 0 && (
        <div className="bg-slate-800 border border-blue-700 rounded-2xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <ShoppingCart className="w-5 h-5 text-blue-400" />
              {t('seat.cart_title')} ({selectedSeats.length})
            </h3>
            <button onClick={clearSeats} className="text-slate-400 hover:text-white text-xs">
              {t('seat.cart_clear')}
            </button>
          </div>
          <div className="space-y-2">
            {selectedSeats.map(s => (
              <div key={s.seat_id} className="flex items-center justify-between bg-slate-900 rounded-xl px-3 py-2">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-blue-300 text-sm">{s.seat_number}</span>
                  <span className="text-slate-400 text-xs">
                    {s.seat_class === 'FIRST' ? '👑 First' : '🪑 Economy'}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-white font-semibold">${s.price?.toFixed(2)}</span>
                  <button onClick={() => removeSeat(s.seat_id)}
                    className="text-slate-500 hover:text-red-400 transition-colors">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between border-t border-slate-700 pt-3">
            <div>
              <div className="text-slate-400 text-xs">{t('seat.cart_total')}</div>
              <div className="text-blue-400 font-bold text-xl">
                ${selectedSeats.reduce((acc, s) => acc + (s.price || 0), 0).toFixed(2)}
              </div>
            </div>
            <button
              onClick={() => setMultiModal(true)}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-5 py-3
                         rounded-xl font-semibold transition-all hover:scale-[1.02]"
            >
              <CreditCard className="w-4 h-4" />
              {t('seat.cart_buy', { count: selectedSeats.length })}
            </button>
          </div>
        </div>
      )}

      {/* Connecting flight purchase modal */}
      {connectingModal && (
        <ConnectingBookingModal
          allLegs={allLegs}
          selectedSeatsPerLeg={selectedSeatsPerLeg}
          sessionToken={sessionToken}
          onClose={() => setConnectingModal(false)}
          t={t}
        />
      )}

      {/* Booking modal (single seat) */}
      {!isConnecting && modalOpen && selectedSeat && (
        <BookingModal
          seat={selectedSeat}
          flight={flight}
          onClose={() => setModalOpen(false)}
          onConfirm={handleModalConfirm}
        />
      )}

      {/* Multi-purchase modal */}
      {multiModal && (
        <MultiPurchaseModal
          seats={selectedSeats}
          flight={flight}
          sessionToken={sessionToken}
          onClose={() => setMultiModal(false)}
          onSuccess={(result) => {
            setMultiModal(false)
            clearSeats()
            setMultiMode(false)
            setMultiSuccess(result)
            loadSeats()
          }}
          t={t}
        />
      )}

      {/* Multi-purchase success */}
      {multiSuccess && (
        <MultiSuccessModal
          result={multiSuccess}
          flight={flight}
          onClose={() => setMultiSuccess(null)}
          t={t}
          BASE={BASE}
        />
      )}
    </div>
  )
}

// ─── Multi-purchase modal ─────────────────────────────────────────────────────
function MultiPurchaseModal({ seats, flight, sessionToken, onClose, onSuccess, t }) {
  const navigate = useNavigate()
  const [passport, setPassport] = useState('')
  const [passengerName, setPassengerName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleBuy = async () => {
    if (!passport || !passengerName) { setError(t('booking.enter_passport')); return }
    setLoading(true); setError('')
    try {
      const result = await purchaseMultiple({
        seat_ids: seats.map(s => s.seat_id),
        session_token: sessionToken || `ui-${Date.now()}`,
        passport: passport.toUpperCase(),
        full_name: passengerName,
        flight_id: flight.flight_id,
      })
      // Redirigir directo al boarding pass (clearSeats se dispara en cleanup de SeatSelection)
      const tickets = result.tickets || []
      if (tickets.length === 1) {
        navigate(`/ticket/${tickets[0].ticket_id}`)
      } else if (tickets.length > 1) {
        navigate(`/ticket/${tickets[0].ticket_id}`, {
          state: { allTickets: tickets },
        })
      } else {
        // Fallback: sin ticket_ids → usar modal antiguo
        onSuccess(result)
      }
    } catch (e) {
      setError(e.message || t('booking.error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/75 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-semibold text-lg">
            {t('seat.cart_buy', { count: seats.length })}
          </h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="bg-slate-900 rounded-xl p-3 space-y-1.5 text-sm">
          {seats.map(s => (
            <div key={s.seat_id} className="flex justify-between">
              <span className="text-slate-400 font-mono">{s.seat_number}</span>
              <span className="text-white">${s.price?.toFixed(2)}</span>
            </div>
          ))}
          <div className="flex justify-between border-t border-slate-700 pt-2 mt-2 font-bold">
            <span className="text-slate-300">{t('seat.cart_total')}</span>
            <span className="text-blue-400">
              ${seats.reduce((a, s) => a + (s.price || 0), 0).toFixed(2)}
            </span>
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-slate-400 text-sm mb-1 block">{t('booking.passport')}</label>
            <input value={passport} onChange={e => setPassport(e.target.value.toUpperCase())}
              placeholder="AB123456"
              className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2.5 text-white
                font-mono focus:outline-none focus:border-blue-500"
              maxLength={20} />
          </div>
          <div>
            <label className="text-slate-400 text-sm mb-1 block">{t('booking.full_name')}</label>
            <input value={passengerName} onChange={e => setPassengerName(e.target.value)}
              placeholder="Juan García"
              className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2.5 text-white
                focus:outline-none focus:border-blue-500"
              maxLength={80} />
          </div>
        </div>

        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 rounded-xl p-3 border border-red-800/50">
            {error}
          </div>
        )}

        <button onClick={handleBuy} disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl
            transition-all hover:scale-[1.02] disabled:opacity-50 flex items-center justify-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
          {loading ? t('common.loading') : t('booking.buy')}
        </button>
      </div>
    </div>
  )
}

// ─── Connecting flight purchase modal ─────────────────────────────────────────
function ConnectingBookingModal({ allLegs, selectedSeatsPerLeg, sessionToken, onClose, t }) {
  const navigate = useNavigate()
  const [passport, setPassport] = useState('')
  const [passengerName, setPassengerName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const totalPrice = Object.values(selectedSeatsPerLeg).reduce((sum, s) => sum + (s.price || 0), 0)

  const handleBuy = async () => {
    if (!passport || !passengerName) { setError(t('booking.enter_passport')); return }
    setLoading(true); setError('')
    try {
      const allTicketIds = []
      // Purchase each leg sequentially with the same passenger data
      for (let legIdx = 0; legIdx < allLegs.length; legIdx++) {
        const legSeat = selectedSeatsPerLeg[legIdx]
        if (!legSeat) continue
        const result = await buySeat({
          flight_id: legSeat.flightId,
          seat_id: legSeat.seat_id,
          session_token: sessionToken || `ui-${Date.now()}`,
          passport: passport.toUpperCase(),
          full_name: passengerName,
        })
        if (result?.ticket_id) allTicketIds.push(result.ticket_id)
      }
      if (allTicketIds.length > 0) {
        navigate(`/ticket/${allTicketIds[0]}`, {
          state: {
            allTickets: allTicketIds.map(id => ({ ticket_id: id })),
            isConnecting: true,
          },
        })
      } else {
        onClose()
      }
    } catch (e) {
      setError(e.message || t('booking.error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/75 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-white font-semibold text-lg">Comprar ambos tramos</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Resumen de tramos */}
        <div className="bg-slate-900 rounded-xl p-3 space-y-2 text-sm">
          {allLegs.map((leg, i) => {
            const legSeat = selectedSeatsPerLeg[i]
            return (
              <div key={i} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-blue-400 font-mono text-xs font-bold">
                    {leg.origin} → {leg.destination}
                  </span>
                  {legSeat && (
                    <span className="text-slate-400 font-mono text-xs">· Asiento {legSeat.seat_number}</span>
                  )}
                </div>
                <span className="text-white font-semibold">
                  {legSeat ? `$${legSeat.price?.toFixed(2)}` : <span className="text-slate-500 text-xs">Pendiente</span>}
                </span>
              </div>
            )
          })}
          <div className="flex justify-between border-t border-slate-700 pt-2 mt-1 font-bold">
            <span className="text-slate-300">Total</span>
            <span className="text-blue-400">${totalPrice.toFixed(2)}</span>
          </div>
        </div>

        {/* Datos del pasajero */}
        <div className="space-y-3">
          <div>
            <label className="text-slate-400 text-sm mb-1 block">{t('booking.passport')}</label>
            <input value={passport} onChange={e => setPassport(e.target.value.toUpperCase())}
              placeholder="AB123456"
              className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2.5 text-white
                font-mono focus:outline-none focus:border-blue-500"
              maxLength={20} />
          </div>
          <div>
            <label className="text-slate-400 text-sm mb-1 block">{t('booking.full_name')}</label>
            <input value={passengerName} onChange={e => setPassengerName(e.target.value)}
              placeholder="Juan García"
              className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2.5 text-white
                focus:outline-none focus:border-blue-500"
              maxLength={80} />
          </div>
        </div>

        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 rounded-xl p-3 border border-red-800/50">
            {error}
          </div>
        )}

        <button onClick={handleBuy} disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl
            transition-all hover:scale-[1.02] disabled:opacity-50 flex items-center justify-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
          {loading ? t('common.loading') : `Comprar ${allLegs.length} tramos · $${totalPrice.toFixed(2)}`}
        </button>
      </div>
    </div>
  )
}

// ─── Multi-purchase success modal ─────────────────────────────────────────────
function MultiSuccessModal({ result, flight, onClose, t, BASE }) {
  return (
    <div className="fixed inset-0 bg-black/75 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl p-8 space-y-4">
        <div className="w-16 h-16 bg-green-900/40 border-2 border-green-500 rounded-full
                        flex items-center justify-center mx-auto animate-bounce">
          <CheckCircle className="w-8 h-8 text-green-400" />
        </div>
        <h2 className="text-2xl font-bold text-white text-center">{t('booking.purchase_success')}</h2>
        <p className="text-slate-400 text-sm text-center">{result.passenger_name} · {result.count} tickets</p>

        <div className="space-y-2 max-h-52 overflow-y-auto">
          {(result.tickets || []).map(tk => (
            <div key={tk.ticket_id} className="bg-slate-900 rounded-xl p-3 flex items-center justify-between">
              <div>
                <span className="text-white text-sm font-mono">Ticket #{tk.ticket_id}</span>
                <span className="text-slate-400 text-xs ml-2">Asiento {tk.seat_id}</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => window.open(`${BASE}/api/tickets/${tk.ticket_id}/pdf`, '_blank')}
                  className="text-xs px-2 py-1 bg-blue-700 hover:bg-blue-600 text-white rounded-lg transition-colors"
                >PDF</button>
                <button
                  onClick={() => window.open(`${BASE}/api/tickets/${tk.ticket_id}/wallet`, '_blank')}
                  className="text-xs px-2 py-1 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >Wallet</button>
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-between items-center border-t border-slate-700 pt-3">
          <div>
            <div className="text-slate-400 text-xs">{t('seat.cart_total')}</div>
            <div className="text-blue-400 font-bold text-lg">${result.total_price?.toFixed(2)}</div>
          </div>
          <button onClick={onClose}
            className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-xl font-medium transition-colors">
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  )
}
