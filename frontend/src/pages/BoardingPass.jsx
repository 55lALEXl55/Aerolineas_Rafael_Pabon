/**
 * BoardingPass.jsx — Página standalone optimizada para móvil
 * Ruta: /boarding/:id
 * Sin Layout, sin navegación. Diseño tipo boarding pass real.
 * El usuario puede agregar esta página a su pantalla de inicio.
 */
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { getTicketFull } from '../api'

export default function BoardingPass() {
  const { id } = useParams()
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTicketFull(id)
      .then(setTicket)
      .catch(() => setTicket(null))
      .finally(() => setLoading(false))
  }, [id])

  // Usa IP LAN del backend cuando está disponible — funciona desde celular en la misma red
  const checkinUrl = ticket?.checkin_url
    || `http://${window.location.hostname}/api/tickets/${id}/checkin`

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-white text-center">
          <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Cargando boarding pass…</p>
        </div>
      </div>
    )
  }

  if (!ticket) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center px-4">
          <p className="text-5xl mb-3">❌</p>
          <p className="text-white font-bold">Ticket no encontrado</p>
          <p className="text-slate-400 text-sm mt-1">ID: {id}</p>
        </div>
      </div>
    )
  }

  const isFirst = ticket.seat_class === 'FIRST' || ticket.seat_class === 'FIRST CLASS'

  const statusStyle = {
    PAID:     { bg: 'bg-green-500',  label: 'PAGADO' },
    ACTIVE:   { bg: 'bg-green-500',  label: 'ACTIVO' },
    BOARDED:  { bg: 'bg-blue-500',   label: 'ABORDADO' },
    REFUNDED: { bg: 'bg-red-500',    label: 'REEMBOLSADO' },
    RESERVED: { bg: 'bg-amber-500',  label: 'RESERVADO' },
  }[ticket.status] || { bg: 'bg-gray-600', label: ticket.status }

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center p-4 py-8">
      {/* El boarding pass */}
      <div className="w-full max-w-sm bg-white rounded-3xl overflow-hidden shadow-2xl">

        {/* Header azul marino */}
        <div className="bg-gradient-to-r from-blue-900 to-blue-700 px-5 py-4">
          <div className="text-blue-200 text-xs font-semibold tracking-widest uppercase text-center">
            Aerolíneas Rafael Pabón
          </div>
          <div className="text-white text-2xl font-black tracking-wider text-center mt-0.5">
            BOARDING PASS
          </div>
          <div className="flex justify-center mt-2">
            <span className={`px-3 py-0.5 rounded-full text-xs font-bold ${statusStyle.bg} text-white`}>
              {statusStyle.label}
            </span>
          </div>
        </div>
        <div className="h-1.5 bg-gradient-to-r from-yellow-400 to-yellow-500" />

        {/* Ruta: origen → destino */}
        <div className="bg-slate-50 px-5 py-5 border-b border-dashed border-slate-300">
          <div className="flex items-center justify-center gap-3">
            <div className="text-center">
              <div className="text-5xl font-black text-blue-900 tracking-tight">{ticket.origin}</div>
              <div className="text-slate-500 text-xs mt-0.5 truncate max-w-[90px]">{ticket.origin_city}</div>
              <div className="font-mono text-blue-800 font-bold text-lg mt-1">{ticket.departure_local}</div>
              <div className="text-slate-400 text-xs">LOCAL</div>
            </div>
            <div className="flex flex-col items-center gap-1 px-2">
              <div className="text-2xl">✈</div>
              {ticket.duration_minutes > 0 && (
                <div className="text-slate-400 text-xs text-center">
                  {Math.floor(ticket.duration_minutes / 60)}h {ticket.duration_minutes % 60}m
                </div>
              )}
              <div className="w-12 h-px bg-gradient-to-r from-blue-300 to-blue-600" />
            </div>
            <div className="text-center">
              <div className="text-5xl font-black text-blue-900 tracking-tight">{ticket.destination}</div>
              <div className="text-slate-500 text-xs mt-0.5 truncate max-w-[90px]">{ticket.destination_city}</div>
              <div className="font-mono text-blue-800 font-bold text-lg mt-1">{ticket.arrival_local}</div>
              <div className="text-slate-400 text-xs">LOCAL</div>
            </div>
          </div>
        </div>

        {/* Detalles del pasajero */}
        <div className="px-5 py-4 grid grid-cols-2 gap-x-4 gap-y-3 border-b border-dashed border-slate-300">
          <FieldItem label="PASAJERO" value={ticket.passenger_name} />
          <FieldItem label="PASAPORTE" value={ticket.passport_number} mono />
          <FieldItem label="VUELO" value={ticket.flight_number || `#${ticket.flight_id}`} mono />
          <FieldItem label="FECHA" value={ticket.flight_date} />
          <div>
            <div className="text-slate-400 text-xs tracking-wider">ASIENTO</div>
            <div className="text-blue-700 font-black text-2xl">{ticket.seat_number}</div>
          </div>
          <FieldItem label="CLASE" value={isFirst ? '👑 PRIMERA' : '🪑 ECONOMY'} />
          <FieldItem label="PUERTA" value={ticket.gate || '—'} mono />
          <FieldItem label="PRECIO" value={`$${Number(ticket.total_price || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`} />
        </div>

        {/* QR escaneable — grande para facilitar escaneo con celular */}
        <div className="bg-white px-5 py-6 flex flex-col items-center gap-3">
          <div className="bg-white p-3 rounded-2xl border border-slate-200 shadow-sm">
            <QRCodeSVG
              value={checkinUrl}
              size={220}
              level="M"
              includeMargin={false}
              fgColor="#1e3a5f"
            />
          </div>
          <p className="text-slate-400 text-xs text-center">
            Escanear para registrar abordaje
          </p>
          <p className="text-slate-400 text-xs font-mono">
            #{String(ticket.ticket_id || id).padStart(8, '0')}
          </p>
        </div>

        {/* Footer */}
        <div className="bg-blue-900 px-5 py-2 text-center">
          <p className="text-blue-300 text-xs italic">
            Aerolíneas Rafael Pabón — nunca se atrasa, siempre el precio justo
          </p>
        </div>
      </div>

      <p className="text-slate-500 text-xs mt-4 text-center max-w-xs">
        Tip: en iOS usa <strong className="text-slate-400">Compartir → Agregar a pantalla de inicio</strong> para acceso rápido sin app
      </p>
    </div>
  )
}

function FieldItem({ label, value, mono }) {
  return (
    <div>
      <div className="text-slate-400 text-xs tracking-wider">{label}</div>
      <div className={`text-slate-800 font-semibold text-sm mt-0.5 ${mono ? 'font-mono' : ''}`}>
        {value || '—'}
      </div>
    </div>
  )
}
