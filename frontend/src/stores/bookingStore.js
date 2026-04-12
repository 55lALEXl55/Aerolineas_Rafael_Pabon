import { create } from 'zustand'

export const useBookingStore = create((set, get) => ({
  selectedFlight: null,
  selectedSeat: null,
  purchaseCity: localStorage.getItem('purchaseCity') || '',
  purchaseCityTz: localStorage.getItem('purchaseCityTz') || 'UTC',

  setSelectedFlight: (flight) => set({ selectedFlight: flight }),
  setSelectedSeat: (seat) => set({ selectedSeat: seat }),
  clearSelection: () => set({ selectedFlight: null, selectedSeat: null }),

  setPurchaseCity: (city, tz = 'UTC') => {
    localStorage.setItem('purchaseCity', city)
    localStorage.setItem('purchaseCityTz', tz)
    set({ purchaseCity: city, purchaseCityTz: tz })
  },
}))
