import { useState } from 'react'
import { ChevronDown, ChevronUp, Zap, Maximize2, Gauge } from 'lucide-react'
import { AIRCRAFT_SPECS } from '../utils/seatLayout'

export default function AircraftCard({ model, aircraftId }) {
  const [expanded, setExpanded] = useState(false)
  const spec = AIRCRAFT_SPECS[model]
  if (!spec) return null

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-750 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">✈</span>
          <div className="text-left">
            <div className="font-semibold text-white">{model}</div>
            <div className="text-xs text-slate-400">
              ID #{aircraftId} · {spec.total} asientos · {spec.engines} motores
            </div>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm border-t border-slate-700 pt-3">
          <Stat icon={<Maximize2 className="w-4 h-4" />} label="Longitud" value={spec.length} />
          <Stat icon={<Maximize2 className="w-4 h-4 rotate-90" />} label="Envergadura" value={spec.wingspan} />
          <Stat icon={<Gauge className="w-4 h-4" />} label="Crucero" value={spec.cruiseSpeed} />
          <Stat icon={<Zap className="w-4 h-4" />} label="Alcance" value={spec.range} />
          <div className="col-span-2 flex gap-4">
            <div>
              <div className="text-slate-500 text-xs">Primera</div>
              <div className="text-amber-400 font-bold">{spec.seatsFirst}</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs">Turista</div>
              <div className="text-blue-400 font-bold">{spec.seatsEconomy}</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs">Motores</div>
              <div className="text-white font-bold">{spec.engines}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ icon, label, value }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-500">{icon}</span>
      <div>
        <div className="text-slate-500 text-xs">{label}</div>
        <div className="text-white text-sm font-medium">{value}</div>
      </div>
    </div>
  )
}
