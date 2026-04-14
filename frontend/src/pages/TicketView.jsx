import { useState, useEffect } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { Plane, User, CreditCard, Calendar, MapPin, Download, ArrowLeft, CheckCircle, Clock, Smartphone } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { getTicketFull } from '../api'
import { getAirportTz } from '../utils/geoRouter'

const BASE = import.meta.env.VITE_API_URL || ''

export default function TicketView() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const allTickets = location.state?.allTickets || []
  const [ticket, setTicket] = useState(null)
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)

  // URL que el QR contiene — usa IP LAN del backend para funcionar desde celular
  // ticket.checkin_url viene del backend con la IP real de red (no localhost)
  const checkinUrl = ticket?.checkin_url || `http://${window.location.hostname}/api/tickets/${id}/checkin`

  const downloadPdf = async () => {
    setDownloading(true)
    try {
      const res = await fetch(`${BASE}/api/tickets/${id}/pdf`)
      if (!res.ok) throw new Error('Error al generar PDF')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `boarding-pass-${id}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      alert(e.message)
    } finally {
      setDownloading(false)
    }
  }

  useEffect(() => {
    getTicketFull(id)
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

  const statusBadge = {
    PAID:    { cls: 'bg-green-500 text-white',  label: 'PAGADO' },
    ACTIVE:  { cls: 'bg-green-500 text-white',  label: 'ACTIVO' },
    BOARDED: { cls: 'bg-blue-500 text-white',   label: 'ABORDADO' },
    REFUNDED:{ cls: 'bg-red-500 text-white',    label: 'REEMBOLSADO' },
    RESERVED:{ cls: 'bg-amber-500 text-white',  label: 'RESERVADO' },
  }[ticket.status] || { cls: 'bg-gray-600 text-white', label: ticket.status }

  const isFirstClass = ticket.seat_class === 'FIRST' || ticket.seat_class === 'FIRST CLASS'

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-[fadeIn_0.3s_ease-out]">
      {/* Nav + éxito */}
      <div className="flex items-center justify-between">
        <button onClick={() => navigate('/')}
          className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors text-sm">
          <ArrowLeft className="w-4 h-4" /> Volver a búsqueda
        </button>
        <div className="flex items-center gap-2 text-green-400 text-sm font-medium">
          <CheckCircle className="w-4 h-4" />
          Compra confirmada
        </div>
      </div>

      {/* ── BOARDING PASS ────────────────────────────────────────── */}
      <div className="bg-white rounded-3xl overflow-hidden shadow-2xl border border-slate-200">

        {/* Header azul marino */}
        <div className="bg-gradient-to-r from-blue-900 to-blue-700 px-6 py-4 flex items-center justify-between">
          <div>
            <div className="text-blue-200 text-xs font-semibold tracking-widest uppercase">
              Aerolíneas Rafael Pabón
            </div>
            <div className="text-white text-xl font-bold mt-0.5 tracking-wider">
              BOARDING PASS
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-bold tracking-wide ${statusBadge.cls}`}>
            {statusBadge.label}
          </span>
        </div>

        {/* Franja dorada */}
        <div className="h-1.5 bg-gradient-to-r from-yellow-400 to-yellow-500" />

        {/* Ruta principal */}
        <div className="bg-slate-50 px-6 py-5 border-b border-dashed border-slate-300">
          <div className="flex items-center justify-between gap-4">
            {/* Origen */}
            <div className="flex-1">
              <div className="text-5xl font-black text-blue-900 tracking-tight">{ticket.origin}</div>
              <div className="text-slate-500 text-sm mt-1">{ticket.origin_city}</div>
              <div className="text-slate-700 font-mono text-lg font-bold mt-2">
                {ticket.departure_local}
                <span className="text-slate-400 text-xs font-normal ml-1">LOCAL</span>
              </div>
            </div>

            {/* Centro */}
            <div className="flex flex-col items-center gap-1 px-2">
              <Plane className="w-7 h-7 text-blue-500" />
              {ticket.duration_minutes > 0 && (
                <div className="flex items-center gap-1 text-slate-500 text-xs">
                  <Clock className="w-3 h-3" />
                  {Math.floor(ticket.duration_minutes / 60)}h {ticket.duration_minutes % 60}m
                </div>
              )}
              <div className="w-16 h-px bg-gradient-to-r from-blue-300 to-blue-600" />
            </div>

            {/* Destino */}
            <div className="flex-1 text-right">
              <div className="text-5xl font-black text-blue-900 tracking-tight">{ticket.destination}</div>
              <div className="text-slate-500 text-sm mt-1">{ticket.destination_city}</div>
              <div className="text-slate-700 font-mono text-lg font-bold mt-2">
                {ticket.arrival_local}
                <span className="text-slate-400 text-xs font-normal ml-1">LOCAL</span>
              </div>
            </div>
          </div>
        </div>

        {/* Detalles del pasajero + vuelo */}
        <div className="px-6 py-4 grid grid-cols-2 gap-x-6 gap-y-3 border-b border-dashed border-slate-300">
          <Detail icon={<User className="w-4 h-4" />}     label="PASAJERO"      value={ticket.passenger_name || '—'} />
          <Detail icon={<CreditCard className="w-4 h-4" />} label="PASAPORTE"   value={ticket.passport_number || '—'} mono />
          <Detail icon={<Plane className="w-4 h-4" />}    label="VUELO"         value={ticket.flight_number || '—'} mono />
          <Detail icon={<Calendar className="w-4 h-4" />} label="FECHA"         value={ticket.flight_date || '—'} />
          <Detail icon={<MapPin className="w-4 h-4" />}   label="ASIENTO"       value={ticket.seat_number || '—'} mono accent />
          <Detail
            icon={<span className="text-sm">{isFirstClass ? '👑' : '🪑'}</span>}
            label="CLASE"
            value={isFirstClass ? 'PRIMERA' : 'ECONOMY'}
          />
          <Detail
            icon={<span className="text-sm">🚪</span>}
            label="PUERTA"
            value={ticket.gate || '—'}
            mono
          />
          <Detail
            icon={<span className="text-sm">💵</span>}
            label="PRECIO"
            value={`$${Number(ticket.total_price || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })} USD`}
          />
        </div>

        {/* QR escaneable */}
        <div className="bg-slate-50 px-6 py-5 flex flex-col items-center gap-2">
          <div className="bg-white p-3 rounded-2xl shadow-sm border border-slate-200">
            <QRCodeSVG
              value={checkinUrl}
              size={160}
              level="M"
              includeMargin={false}
              fgColor="#1e3a5f"
            />
          </div>
          <p className="text-xs text-slate-400 text-center">
            Escanear para registrar abordaje
          </p>
          <p className="text-xs text-slate-300 font-mono">
            #{String(ticket.ticket_id || id).padStart(8, '0')}
          </p>
        </div>

        {/* Footer */}
        <div className="bg-blue-900 px-6 py-2 text-center">
          <p className="text-blue-300 text-xs italic">
            Aerolíneas Rafael Pabón — nunca se atrasa, siempre el precio justo
          </p>
        </div>
      </div>

      {/* Botones: PDF + Boarding Pass Digital */}
      <div className="flex gap-3">
        <button
          onClick={downloadPdf}
          disabled={downloading}
          className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500
            text-white py-3 rounded-xl font-semibold transition-all hover:shadow-lg
            hover:shadow-blue-900/40 disabled:opacity-60"
        >
          <Download className="w-4 h-4" />
          {downloading ? 'Generando…' : 'PDF'}
        </button>
        <button
          onClick={() => window.open(`/boarding/${id}`, '_blank')}
          className="flex-1 flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600
            text-white py-3 rounded-xl font-semibold transition-all"
        >
          <Smartphone className="w-4 h-4" />
          Boarding Digital
        </button>
      </div>

      {/* Otros tickets de la misma compra */}
      {allTickets.length > 1 && (
        <div className="bg-slate-800 border border-slate-700 rounded-2xl p-4">
          <h4 className="text-slate-300 font-semibold text-sm mb-3">
            Otros boletos de esta compra ({allTickets.length - 1} más)
          </h4>
          <div className="space-y-2">
            {allTickets
              .filter(tk => String(tk.ticket_id) !== String(id))
              .map(tk => (
                <button
                  key={tk.ticket_id}
                  onClick={() => navigate(`/ticket/${tk.ticket_id}`, { state: { allTickets } })}
                  className="w-full flex items-center justify-between bg-slate-900 hover:bg-slate-800
                    rounded-xl px-4 py-2.5 transition-colors text-left"
                >
                  <div>
                    <span className="text-white text-sm font-mono">Ticket #{tk.ticket_id}</span>
                    <span className="text-slate-400 text-xs ml-2">Asiento {tk.seat_id}</span>
                  </div>
                  <span className="text-blue-400 text-xs">Ver →</span>
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Detail({ icon, label, value, mono, accent }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-blue-400 mt-0.5 shrink-0">{icon}</span>
      <div>
        <div className="text-slate-400 text-xs tracking-wider">{label}</div>
        <div className={`mt-0.5 font-semibold text-sm
          ${accent ? 'text-blue-700 text-lg font-black' : 'text-slate-800'}
          ${mono ? 'font-mono' : ''}`}>
          {value}
        </div>
      </div>
    </div>
  )
}
