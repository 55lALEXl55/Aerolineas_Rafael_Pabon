import { create } from 'zustand'
import { getDashboardSyncStatus } from '../api'

export const useSyncStore = create((set, get) => ({
  nodes: { db1: null, db2: null, db3: null },
  globalStatus: 'unknown', // 'aligned' | 'pending' | 'conflict'
  lastUpdated: null,
  intervalId: null,

  startPolling: () => {
    if (get().intervalId) return
    const poll = async () => {
      try {
        const data = await getDashboardSyncStatus()
        // Map actual API response to node format expected by SyncStatus component
        const svcs = data.services || {}
        const conflicts = data.sync_stats?.conflicts_detected || 0
        const nodes = {
          db1: { delay_ms: svcs['ms-flights']?.latency_ms ?? 0, status: svcs['ms-flights']?.status },
          db2: { delay_ms: svcs['ms-bookings']?.latency_ms ?? 0, status: svcs['ms-bookings']?.status },
          db3: { delay_ms: svcs['ms-sync']?.latency_ms ?? 0, status: svcs['ms-sync']?.status },
        }
        const allOk = Object.values(svcs).every(s => s.status === 'OK')
        const globalStatus = conflicts > 0 ? 'conflict' : allOk ? 'aligned' : 'pending'
        set({ nodes, globalStatus, lastUpdated: Date.now() })
      } catch {
        // ignore — show stale data
      }
    }
    poll()
    const id = setInterval(poll, 3000)
    set({ intervalId: id })
  },

  stopPolling: () => {
    const { intervalId } = get()
    if (intervalId) clearInterval(intervalId)
    set({ intervalId: null })
  },

  getNodeColor: (nodeKey) => {
    const node = get().nodes[nodeKey]
    if (!node) return 'gray'
    const delay = node.delay_ms || 0
    if (delay < 3000) return 'green'
    if (delay < 7000) return 'yellow'
    return 'red'
  },
}))
