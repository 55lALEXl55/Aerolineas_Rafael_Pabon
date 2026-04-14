import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Clock, User, CreditCard, AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { reserveSeat, buySeat, refundTicket, cancelReservation, getPassengerByPassport } from '../api'
import { useBookingStore } from '../stores/bookingStore'
import { epochToTime } from '../utils/epochUtils'
import { getAirportTz } from '../utils/geoRouter'
import { STATUS_COLORS, STATUS_TEXT_COLORS } from '../utils/seatLayout'

const NODE_INFO = {
  1: { label: 'DB1 — América',   emoji: '🌎', color: 'text-blue-400',   bg: 'bg-blue-900/20 border-blue-700' },
  2: { label: 'DB2 — Europa/MO', emoji: '🌍', color: 'text-purple-400', bg: 'bg-purple-900/20 border-purple-700' },
  3: { label: 'DB3 — Asia',      emoji: '🌏', color: 'text-orange-400', bg: 'bg-orange-900/20 border-orange-700' },
}

export default function BookingModal({ seat, flight, onClose, onConfirm }) {
  const { t } = useTranslation()
  const { sessionToken, activeNode, setLastTicketId } = useBookingStore()
  const [passport, setPassport] = useState('')
  const [passengerName, setPassengerName] = useState('')
  const [passengerFound, setPassengerFound] = useState(false)
  const [lookingUp, setLookingUp] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [countdown, setCountdown] = useState(null)
  const [now, setNow] = useState(Date.now())
  const [showSuccess, setShowSuccess] = useState(false)
  const debounceRef = useRef(null)

  const status = seat?.status || 'AVAILABLE'
  const nodeInfo = NODE_INFO[activeNode] || NODE_INFO[1]

  // Live clock
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  // Countdown for LOCKED
  useEffect(() => {
    if (status === 'LOCKED' && seat?.locked_until) {
      const remaining = seat.locked_until - Math.floor(Date.now() / 1000)
      setCountdown(Math.max(0, remaining))
      const id = setInterval(() => {
        const r = seat.locked_until - Math.floor(Date.now() / 1000)
        setCountdown(Math.max(0, r))
      }, 1000)
      return () => clearInterval(id)
    }
  }, [status, seat?.locked_until])

  // Debounced passport lookup (400ms)
  const handlePassportChange = (value) => {
    const v = value.toUpperCase()
    setPassport(v)
    setPassengerFound(false)
    setPassengerName('')

    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (v.length < 6) return

    debounceRef.current = setTimeout(async () => {
      setLookingUp(true)
      try {
        const data = await getPassengerByPassport(v)
        if (data?.name || data?.full_name) {
          const name = data.name || data.full_name
          setPassengerName(name)
          setPassengerFound(true)
        }
      } catch { /* not found — user can type name */ }
      finally { setLookingUp(false) }
    }, 400)
  }

  const handleAction = async (action) => {
    if (!passport && action !== 'refund') {
      setError('Ingresa tu número de pasaporte')
      return
    }
    setLoading(true)
    setError('')
    try {
      let result
      const payload = {
        flight_id: flight?.flight_id,
        seat_id: seat?.seat_id,
        session_token: sessionToken || `ui-${Date.now()}`,
        passport: passport,
        full_name: passengerName || passport,
      }
      if (action === 'reserve') result = await reserveSeat(payload)
      else if (action === 'buy') result = await buySeat(payload)
      else if (action === 'confirm') result = await buySeat({ ...payload, booking_id: seat?.booking_id })
      else if (action === 'cancel') result = await cancelReservation(seat?.booking_id)
      else if (action === 'refund') result = await refundTicket(seat?.ticket_id)

      if (result?.ticket_id) setLastTicketId(result.ticket_id)

      setShowSuccess(true)
      setSuccess(t('booking.success'))
      setTimeout(() => { onConfirm?.(); onClose?.() }, 1400)
    } catch (e) {
      setError(e.message || t('booking.error'))
    } finally {
      setLoading(false)
    }
  }

  const originTz = getAirportTz(flight?.origin)
  const destTz   = getAirportTz(flight?.destination)
  const nowSec   = Math.floor(now / 1000)

  return (
    <div className="fixed inset-0 bg-black/75 flex items-center justify-center z-50 p-4
                    animate-[fadeIn_0.15s_ease-out]">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl
                      animate-[fadeSlideUp_0.2s_ease-out]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-700">
          <div>
            <h3 className="text-white font-semibold text-lg">
              {t('booking.seat')} <span className="text-blue-400 font-mono">{seat?.seat_number}</span>
            </h3>
            <p className="text-slate-400 text-sm">
              {seat?.seat_class === 'FIRST' ? '👑 ' + t('seat.first') : '🪑 ' + t('seat.economy')}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Processing node indicator */}
          <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg border ${nodeInfo.bg}`}>
            <span className="w-2 h-2 rounded-full bg-green-400 shrink-0" />
            <span className="text-slate-400">Procesando en:</span>
            <span className={`font-semibold ${nodeInfo.color}`}>{nodeInfo.emoji} {nodeInfo.label}</span>
          </div>

          {/* Status + Price */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-900 rounded-xl p-3">
              <div className="text-slate-500 text-xs mb-1">{t('booking.status')}</div>
              <div className={`font-semibold ${STATUS_TEXT_COLORS[status]}`}>{t(`status.${status}`)}</div>
            </div>
            <div className="bg-slate-900 rounded-xl p-3">
              <div className="text-slate-500 text-xs mb-1">{t('booking.price')}</div>
              <div className="text-white font-bold text-xl">${seat?.price?.toFixed(2)}</div>
            </div>
          </div>

          {/* Live local times */}
          <div className="bg-slate-900 rounded-xl p-3 grid grid-cols-2 gap-3">
            <div>
              <div className="text-slate-500 text-xs">{flight?.origin} (local)</div>
              <div className="text-white font-mono text-sm">{epochToTime(nowSec, originTz)}</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs">{flight?.destination} (local)</div>
              <div className="text-white font-mono text-sm">{epochToTime(nowSec, destTz)}</div>
            </div>
          </div>

          {/* LOCKED countdown */}
          {status === 'LOCKED' && (
            <div className="bg-gray-900 border border-gray-700 rounded-xl p-3 flex items-center gap-2">
              <Clock className="w-5 h-5 text-gray-400 shrink-0" />
              <div>
                <p className="text-gray-300 text-sm">{t('booking.locked_msg')}</p>
                {countdown !== null && (
                  <p className="text-gray-400 text-xs font-mono mt-0.5">Disponible en: {countdown}s</p>
                )}
              </div>
            </div>
          )}

          {/* Passport input with autocomplete */}
          {status !== 'LOCKED' && (
            <div className="space-y-3">
              <div>
                <label className="text-slate-400 text-sm mb-1 flex items-center gap-1">
                  <User className="w-3 h-3" />
                  {t('booking.passport')}
                </label>
                <div className="relative">
                  <input
                    value={passport}
                    onChange={e => handlePassportChange(e.target.value)}
                    placeholder="AB123456"
                    className="w-full bg-slate-900 border border-slate-600 rounded-xl px-3 py-2.5 text-white
                      focus:outline-none focus:border-blue-500 font-mono transition-colors pr-10"
                    maxLength={20}
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    {lookingUp && <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />}
                    {!lookingUp && passengerFound && <CheckCircle className="w-4 h-4 text-green-400" />}
                  </div>
                </div>
                {passengerFound && (
                  <p className="text-green-400 text-xs mt-1.5 flex items-center gap-1 animate-[fadeIn_0.2s_ease-out]">
                    <CheckCircle className="w-3 h-3" />
                    Pasajero registrado: <span className="font-semibold">{passengerName}</span>
                  </p>
                )}
              </div>

              <div>
                <label className="text-slate-400 text-sm mb-1 block">
                  {t('booking.full_name')}
                </label>
                <input
                  value={passengerName}
                  onChange={e => !passengerFound && setPassengerName(e.target.value)}
                  readOnly={passengerFound}
                  placeholder="Juan García"
                  className={`w-full bg-slate-900 border rounded-xl px-3 py-2.5 text-white
                    focus:outline-none transition-colors
                    ${passengerFound
                      ? 'border-green-700/50 text-slate-400 cursor-not-allowed'
                      : 'border-slate-600 focus:border-blue-500'}`}
                  maxLength={80}
                />
              </div>
            </div>
          )}

          {/* Success animation */}
          {showSuccess && (
            <div className="flex flex-col items-center py-4 animate-[fadeSlideUp_0.3s_ease-out]">
              <div className="w-16 h-16 rounded-full bg-green-900/40 border-2 border-green-500
                              flex items-center justify-center mb-3 animate-[pulse_0.6s_ease-out]">
                <CheckCircle className="w-8 h-8 text-green-400" />
              </div>
              <p className="text-green-400 font-semibold">{success}</p>
            </div>
          )}

          {/* Error */}
          {error && !showSuccess && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 rounded-xl p-3 border border-red-800/50">
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}

          {/* Action buttons */}
          {!showSuccess && status === 'AVAILABLE' && (
            <div className="flex gap-3">
              <button onClick={() => handleAction('reserve')} disabled={loading}
                className="flex-1 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-medium
                  transition-all hover:scale-[1.02] disabled:opacity-50 disabled:scale-100">
                {loading ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : t('booking.reserve')}
              </button>
              <button onClick={() => handleAction('buy')} disabled={loading}
                className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium
                  transition-all hover:scale-[1.02] disabled:opacity-50 disabled:scale-100 flex items-center justify-center gap-1.5">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (
                  <><CreditCard className="w-4 h-4" />{t('booking.buy')}</>
                )}
              </button>
            </div>
          )}
          {!showSuccess && status === 'RESERVED' && (
            <div className="flex gap-3">
              <button onClick={() => handleAction('cancel')} disabled={loading}
                className="flex-1 py-2.5 rounded-xl bg-red-700 hover:bg-red-600 text-white font-medium
                  transition-all hover:scale-[1.02] disabled:opacity-50 disabled:scale-100">
                {t('booking.cancel')}
              </button>
              <button onClick={() => handleAction('confirm')} disabled={loading}
                className="flex-1 py-2.5 rounded-xl bg-green-600 hover:bg-green-500 text-white font-medium
                  transition-all hover:scale-[1.02] disabled:opacity-50 disabled:scale-100">
                {t('booking.confirm')}
              </button>
            </div>
          )}
          {!showSuccess && status === 'SOLD' && (
            <button onClick={() => handleAction('refund')} disabled={loading}
              className="w-full py-2.5 rounded-xl bg-red-700 hover:bg-red-600 text-white font-medium
                transition-all hover:scale-[1.02] disabled:opacity-50 disabled:scale-100">
              {t('booking.refund')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
