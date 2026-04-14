import { useBookingStore } from '../stores/bookingStore'

const NODES = [
  { id: 1, label: 'DB1', region: 'América',   emoji: '🌎', color: 'blue',   airports: 'ATL LAX DFW SAO' },
  { id: 2, label: 'DB2', region: 'Europa/MO', emoji: '🌍', color: 'purple', airports: 'LON PAR FRA IST MAD AMS DXB' },
  { id: 3, label: 'DB3', region: 'Asia',      emoji: '🌏', color: 'orange', airports: 'PEK TYO SIN CAN' },
]

const ACTIVE = {
  blue:   'bg-blue-600   border-blue-500   text-white',
  purple: 'bg-purple-600 border-purple-500 text-white',
  orange: 'bg-orange-500 border-orange-400 text-white',
}
const IDLE = 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white'

export default function NodeSelector({ compact = false }) {
  const { activeNode, setActiveNode } = useBookingStore()

  return (
    <div className={`flex gap-2 ${compact ? '' : 'flex-wrap'}`}>
      {NODES.map(n => {
        const isActive = activeNode === n.id
        return (
          <button
            key={n.id}
            onClick={() => setActiveNode(n.id)}
            className={`flex items-center gap-1.5 border rounded-lg transition-all
              ${compact ? 'px-2.5 py-1 text-xs' : 'px-3 py-2 text-sm'}
              ${isActive ? ACTIVE[n.color] : IDLE}`}
          >
            <span>{n.emoji}</span>
            <span className="font-semibold">{n.label}</span>
            {!compact && <span className="opacity-80">— {n.region}</span>}
          </button>
        )
      })}
    </div>
  )
}

export { NODES }
