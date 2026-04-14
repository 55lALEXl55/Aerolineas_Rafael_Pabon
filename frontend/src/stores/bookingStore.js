import { create } from 'zustand'

export const useBookingStore = create((set) => ({
  selectedFlight: null,
  selectedSeat: null,
  sessionToken: null,
  purchaseCity: localStorage.getItem('purchaseCity') || '',
  purchaseCityTz: localStorage.getItem('purchaseCityTz') || 'UTC',
  activeNode: parseInt(localStorage.getItem('activeNode') || '1'),
  lastTicketId: localStorage.getItem('lastTicketId') || null,

  setSelectedFlight: (flight) => set({ selectedFlight: flight }),
  setSelectedSeat: (seat) => set({ selectedSeat: seat }),
  setSessionToken: (token) => set({ sessionToken: token }),
  clearSelection: () => set({ selectedFlight: null, selectedSeat: null, sessionToken: null }),

  setActiveNode: (node) => {
    localStorage.setItem('activeNode', String(node))
    set({ activeNode: node })
  },
  setLastTicketId: (id) => {
    localStorage.setItem('lastTicketId', String(id))
    set({ lastTicketId: id })
  },
  setPurchaseCity: (city, tz = 'UTC') => {
    localStorage.setItem('purchaseCity', city)
    localStorage.setItem('purchaseCityTz', tz)
    set({ purchaseCity: city, purchaseCityTz: tz })
  },
}))
