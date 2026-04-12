import { useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'
import { useSyncStore } from '../../stores/syncStore'

export default function Layout() {
  const { startPolling, stopPolling } = useSyncStore()

  useEffect(() => {
    startPolling()
    return () => stopPolling()
  }, [])

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <Navbar />
      <main className="flex-1 container mx-auto px-4 py-6 max-w-7xl">
        <Outlet />
      </main>
    </div>
  )
}
