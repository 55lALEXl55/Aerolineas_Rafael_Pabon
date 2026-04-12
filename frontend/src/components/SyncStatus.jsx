import { useSyncStore } from '../stores/syncStore'

const DOT_COLOR = { green: 'bg-green-400', yellow: 'bg-yellow-400', red: 'bg-red-500', gray: 'bg-gray-500' }

export default function SyncStatus() {
  const { nodes, globalStatus, getNodeColor } = useSyncStore()

  const colors = {
    db1: getNodeColor('db1'),
    db2: getNodeColor('db2'),
    db3: getNodeColor('db3'),
  }

  return (
    <div className="flex items-center gap-1.5 text-xs text-slate-400" title={`Sync: ${globalStatus}`}>
      {['db1','db2','db3'].map((k) => (
        <span key={k} className="flex items-center gap-0.5">
          <span className={`w-2 h-2 rounded-full ${DOT_COLOR[colors[k]]} ${colors[k] === 'green' ? '' : 'animate-pulse'}`} />
        </span>
      ))}
      <span className="hidden sm:block font-mono">
        {globalStatus === 'aligned' ? '✓' : globalStatus === 'conflict' ? '!' : '…'}
      </span>
    </div>
  )
}
