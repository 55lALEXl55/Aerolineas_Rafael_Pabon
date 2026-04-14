import { create } from 'zustand'

export const useBookingStore = create((set) => ({
  selectedFlight: null,
  selectedSeat: null,
  sessionToken: null,
  selectedClass: localStorage.getItem('selectedClass') || 'ECONOMY',
  purchaseCity: localStorage.getItem('purchaseCity') || '',
  purchaseCityTz: localStorage.getItem('purchaseCityTz') || 'UTC',
  activeNode: parseInt(localStorage.getItem('activeNode') || '1'),
  lastTicketId: localStorage.getItem('lastTicketId') || null,
  selectedSeats: [],  // multi-seat selection

  setSelectedFlight: (flight) => set({ selectedFlight: flight }),
  setSelectedSeat: (seat) => set({ selectedSeat: seat }),
  setSessionToken: (token) => set({ sessionToken: token }),
  setSelectedClass: (cls) => {
    localStorage.setItem('selectedClass', cls)
    set({ selectedClass: cls })
  },
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
  addSeat: (seat) => set((state) => ({
    selectedSeats: state.selectedSeats.some(s => s.seat_id === seat.seat_id)
      ? state.selectedSeats
      : [...state.selectedSeats, seat],
  })),
  removeSeat: (seatId) => set((state) => ({
    selectedSeats: state.selectedSeats.filter(s => s.seat_id !== seatId),
  })),
  clearSeats: () => set({ selectedSeats: [] }),
}))
