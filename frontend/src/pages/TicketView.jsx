import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Plane, User, CreditCard, Calendar, MapPin } from 'lucide-react'
import { getTicket } from '../api'
import { epochToLocal, epochToTime, durationStr } from '../utils/epochUtils'
import { getAirportName, getAirportTz } from '../utils/geoRouter'
import { STATUS_TEXT_COLORS } from '../utils/seatLayout'

export default function TicketView() {
  const { id } = useParams()
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTicket(id)
      .then(setTicket)
      .catch(() => setTicket(null))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-400">Cargando ticket...</div>
  )
  if (!ticket) return (
    <div className="flex items-center justify-center h-64 text-slate-500">Ticket no encontrado</div>
  )

  const originTz = getAirportTz(ticket.origin)
  const destTz = getAirportTz(ticket.destination)

  return (
    <div className="max-w-2xl mx-auto">
      {/* Boarding pass style */}
      <div className="bg-slate-800 border border-slate-700 rounded-3xl overflow-hidden shadow-2xl">
        {/* Top */}
        <div className="bg-gradient-to-r from-blue-900 to-blue-700 p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-blue-200 text-sm font-medium">Aerolíneas Rafael Pabón</div>
              <div className="text-white font-bold text-2xl mt-1">{ticket.flight_number}</div>
            </div>
            <div className={`px-3 py-1 rounded-full text-sm font-medium
              ${ticket.status === 'ACTIVE' ? 'bg-green-500 text-white' :
                ticket.status === 'REFUNDED' ? 'bg-red-500 text-white' :
                'bg-gray-600 text-white'}`}>
              {ticket.status}
            </div>
          </div>
        </div>

        {/* Route */}
        <div className="p-6 border-b border-dashed border-slate-600">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-4xl font-bold text-white">{ticket.origin}</div>
              <div className="text-slate-400 text-sm">{getAirportName(ticket.origin)}</div>
              <div className="text-slate-300 font-mono mt-1">{epochToTime(ticket.departure_epoch, originTz)}</div>
              <div className="text-slate-500 text-xs">{epochToLocal(ticket.departure_epoch, originTz)}</div>
            </div>
            <div className="flex flex-col items-center">
              <Plane className="w-8 h-8 text-blue-400" />
              <div className="text-slate-500 text-xs mt-1">{durationStr(ticket.duration_minutes)}</div>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold text-white">{ticket.destination}</div>
              <div className="text-slate-400 text-sm">{getAirportName(ticket.destination)}</div>
              <div className="text-slate-300 font-mono mt-1">{epochToTime(ticket.arrival_epoch, destTz)}</div>
              <div className="text-slate-500 text-xs">{epochToLocal(ticket.arrival_epoch, destTz)}</div>
            </div>
          </div>
        </div>

        {/* Details */}
        <div className="p-6 grid grid-cols-2 gap-4 text-sm">
          <Detail icon={<User className="w-4 h-4" />} label="Pasajero" value={ticket.passenger_name || '—'} />
          <Detail icon={<CreditCard className="w-4 h-4" />} label="Pasaporte" value={ticket.passport_number || '—'} mono />
          <Detail icon={<MapPin className="w-4 h-4" />} label="Asiento" value={`${ticket.seat_number} · ${ticket.seat_class}`} />
          <Detail icon={<Calendar className="w-4 h-4" />} label="Emitido" value={epochToLocal(ticket.created_at)} />
        </div>

        {/* Barcode area */}
        <div className="bg-slate-900 p-6 text-center">
          <div className="font-mono text-slate-300 text-2xl tracking-widest">
            {String(ticket.ticket_id || '').padStart(8, '0')}
          </div>
          <div className="flex justify-center gap-0.5 mt-3">
            {Array.from({ length: 48 }).map((_, i) => (
              <div
                key={i}
                className="bg-white"
                style={{
                  width: (i % 3 === 0 ? 3 : i % 5 === 0 ? 2 : 1) + 'px',
                  height: i % 7 === 0 ? '40px' : '30px',
                  opacity: 0.8 + (i % 3) * 0.05
                }}
              />
            ))}
          </div>
          <div className="text-slate-500 text-xs mt-2">Ticket ID: {ticket.ticket_id}</div>
        </div>
      </div>
    </div>
  )
}

function Detail({ icon, label, value, mono }) {
  return (
    <div className="flex items-start gap-3">
      <span className="text-slate-500 mt-0.5">{icon}</span>
      <div>
        <div className="text-slate-400 text-xs">{label}</div>
        <div className={`text-white ${mono ? 'font-mono' : 'font-medium'}`}>{value}</div>
      </div>
    </div>
  )
}
