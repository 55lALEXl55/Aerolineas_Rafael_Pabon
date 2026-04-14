import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Navbar from './Navbar'
import { useSyncStore } from '../../stores/syncStore'

export default function Layout() {
  const { startPolling, stopPolling } = useSyncStore()
  const location = useLocation()

  useEffect(() => {
    startPolling()
    return () => stopPolling()
  }, [])

  const isAdmin = location.pathname.startsWith('/admin')

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <Navbar isAdmin={isAdmin} />
      <main className="flex-1 container mx-auto px-4 py-6 max-w-7xl">
        <div key={location.pathname} className="animate-[fadeIn_0.2s_ease-out]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
