import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Clock, User, CreditCard, AlertCircle } from 'lucide-react'
import { reserveSeat, buySeat, refundTicket, cancelReservation, getPassengerByPassport } from '../api'
import { epochToTime } from '../utils/epochUtils'
import { getAirportTz } from '../utils/geoRouter'
import { STATUS_COLORS, STATUS_TEXT_COLORS } from '../utils/seatLayout'

export default function BookingModal({ seat, flight, onClose, onConfirm }) {
  const { t } = useTranslation()
  const [passport, setPassport] = useState('')
  const [passengerName, setPassengerName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [countdown, setCountdown] = useState(null)
  const [now, setNow] = useState(Date.now())

  const status = seat?.status || 'AVAILABLE'

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

  // Passport autocomplete
  const handlePassportBlur = async () => {
    if (passport.length < 6) return
    try {
      const data = await getPassengerByPassport(passport)
      if (data?.name) setPassengerName(data.name)
    } catch { /* not found */ }
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
        seat_number: seat?.seat_number,
        passport_number: passport,
        passenger_name: passengerName,
        purchase_city: localStorage.getItem('purchaseCity') || '',
      }
      if (action === 'reserve') result = await reserveSeat(payload)
      else if (action === 'buy') result = await buySeat(payload)
      else if (action === 'confirm') result = await buySeat({ ...payload, booking_id: seat?.booking_id })
      else if (action === 'cancel') result = await cancelReservation(seat?.booking_id)
      else if (action === 'refund') result = await refundTicket(seat?.ticket_id)

      setSuccess(t('booking.success'))
      setTimeout(() => { onConfirm?.(); onClose?.() }, 1200)
    } catch (e) {
      setError(e.message || t('booking.error'))
    } finally {
      setLoading(false)
    }
  }

  const originTz = getAirportTz(flight?.origin)
  const destTz = getAirportTz(flight?.destination)
  const nowSec = Math.floor(now / 1000)

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-700">
          <div>
            <h3 className="text-white font-semibold text-lg">
              {t('booking.seat')} <span className="text-blue-400">{seat?.seat_number}</span>
            </h3>
            <p className="text-slate-400 text-sm">{seat?.seat_class === 'FIRST' ? t('seat.first') : t('seat.economy')}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Status */}
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-sm">{t('booking.status')}</span>
            <span className={`font-semibold ${STATUS_TEXT_COLORS[status]}`}>{t(`status.${status}`)}</span>
          </div>

          {/* Price */}
          <div className="flex items-center justify-between">
            <span className="text-slate-400 text-sm">{t('booking.price')}</span>
            <span className="text-white font-bold text-xl">${seat?.price?.toFixed(2)}</span>
          </div>

          {/* Live times */}
          <div className="bg-slate-900 rounded-lg p-3 grid grid-cols-2 gap-3">
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
            <div className="bg-gray-900 border border-gray-600 rounded-lg p-3 flex items-center gap-2">
              <Clock className="w-5 h-5 text-gray-400" />
              <div>
                <p className="text-gray-300 text-sm">{t('booking.locked_msg')}</p>
                {countdown !== null && (
                  <p className="text-gray-400 text-xs font-mono mt-1">
                    Disponible en: {countdown}s
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Passport input */}
          {status !== 'LOCKED' && (
            <div>
              <label className="text-slate-400 text-sm mb-1 block">
                <User className="w-3 h-3 inline mr-1" />
                {t('booking.passport')}
              </label>
              <input
                value={passport}
                onChange={e => setPassport(e.target.value.toUpperCase())}
                onBlur={handlePassportBlur}
                placeholder="AB123456"
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-white
                  focus:outline-none focus:border-blue-500 font-mono"
                maxLength={20}
              />
              {passengerName && (
                <p className="text-green-400 text-xs mt-1">✓ {passengerName}</p>
              )}
            </div>
          )}

          {/* Error / Success */}
          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 rounded-lg p-2">
              <AlertCircle className="w-4 h-4 shrink-0" /> {error}
            </div>
          )}
          {success && (
            <div className="text-green-400 text-sm bg-green-900/20 rounded-lg p-2">✓ {success}</div>
          )}

          {/* Action buttons */}
          {status === 'AVAILABLE' && (
            <div className="flex gap-3">
              <button onClick={() => handleAction('reserve')} disabled={loading}
                className="flex-1 py-2.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium transition-colors disabled:opacity-50">
                {loading ? '...' : t('booking.reserve')}
              </button>
              <button onClick={() => handleAction('buy')} disabled={loading}
                className="flex-1 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium transition-colors disabled:opacity-50">
                <CreditCard className="w-4 h-4 inline mr-1" />
                {loading ? '...' : t('booking.buy')}
              </button>
            </div>
          )}
          {status === 'RESERVED' && (
            <div className="flex gap-3">
              <button onClick={() => handleAction('cancel')} disabled={loading}
                className="flex-1 py-2.5 rounded-lg bg-red-700 hover:bg-red-600 text-white font-medium transition-colors disabled:opacity-50">
                {t('booking.cancel')}
              </button>
              <button onClick={() => handleAction('confirm')} disabled={loading}
                className="flex-1 py-2.5 rounded-lg bg-green-600 hover:bg-green-500 text-white font-medium transition-colors disabled:opacity-50">
                {t('booking.confirm')}
              </button>
            </div>
          )}
          {status === 'SOLD' && (
            <button onClick={() => handleAction('refund')} disabled={loading}
              className="w-full py-2.5 rounded-lg bg-red-700 hover:bg-red-600 text-white font-medium transition-colors disabled:opacity-50">
              {t('booking.refund')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
