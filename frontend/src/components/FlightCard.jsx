import { useTranslation } from 'react-i18next'
import { Plane, Clock, ArrowRight, Tag } from 'lucide-react'
import { epochToDate, epochToTime, durationStr } from '../utils/epochUtils'
import { getAircraftModel } from '../utils/seatLayout'
import { getAirportTz } from '../utils/geoRouter'

export default function FlightCard({ flight, onClick, selected }) {
  const { t } = useTranslation()
  if (!flight) return null

  const model = getAircraftModel(flight.aircraft_id)

  return (
    <div
      onClick={() => onClick?.(flight)}
      className={`bg-slate-800 border rounded-xl p-4 cursor-pointer transition-all hover:border-blue-500
        ${selected ? 'border-blue-500 ring-1 ring-blue-500' : 'border-slate-700'}`}
    >
      <div className="flex items-center justify-between gap-4">
        {/* Route */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="text-center">
            <div className="text-xl font-bold text-white">{flight.origin}</div>
            <div className="text-xs text-slate-400">
              {epochToTime(flight.departure_epoch, getAirportTz(flight.origin))}
              <span className="text-slate-600 ml-0.5">{flight.origin}</span>
            </div>
          </div>
          <div className="flex-1 flex flex-col items-center">
            <div className="text-xs text-slate-500">{durationStr(flight.duration_minutes, t)}</div>
            <div className="flex items-center gap-1 w-full">
              <div className="h-px flex-1 bg-slate-600" />
              <Plane className="w-4 h-4 text-blue-400" />
              <div className="h-px flex-1 bg-slate-600" />
            </div>
            {flight.stopover ? (
              <div className="text-xs text-amber-400">{t('flight.via')} {flight.stopover}</div>
            ) : (
              <div className="text-xs text-green-400">{t('flight.direct')}</div>
            )}
          </div>
          <div className="text-center">
            <div className="text-xl font-bold text-white">{flight.destination}</div>
            <div className="text-xs text-slate-400">
              {epochToTime(
                flight.arrival_epoch || (flight.departure_epoch + (flight.duration_minutes || 0) * 60),
                getAirportTz(flight.destination)
              )}
              <span className="text-slate-600 ml-0.5">{flight.destination}</span>
            </div>
          </div>
        </div>

        {/* Info */}
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-blue-400">${flight.price_economy}</div>
          <div className="text-xs text-slate-400">{model}</div>
          <div className="text-xs text-slate-500">{epochToDate(flight.departure_epoch)}</div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <Tag className="w-3 h-3" />
            {flight.flight_number}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {durationStr(flight.duration_minutes, t)}
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs">
          <span className="text-slate-400">{t('flight.departure')}:</span>
          <span className="text-white">{epochToTime(flight.departure_epoch, getAirportTz(flight.origin))}</span>
          <ArrowRight className="w-3 h-3 text-slate-500" />
          <span className="text-white">
            {epochToTime(
              flight.arrival_epoch || (flight.departure_epoch + (flight.duration_minutes || 0) * 60),
              getAirportTz(flight.destination)
            )}
          </span>
        </div>
      </div>
    </div>
  )
}
