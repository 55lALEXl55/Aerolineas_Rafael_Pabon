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
        set({
          nodes: data.nodes || { db1: null, db2: null, db3: null },
          globalStatus: data.global_status || 'aligned',
          lastUpdated: Date.now(),
        })
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
