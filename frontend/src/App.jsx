import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import FlightSearch from './pages/FlightSearch'
import SeatSelection from './pages/SeatSelection'
import TicketView from './pages/TicketView'
import CompanyDashboard from './pages/CompanyDashboard'
import AdminSync from './pages/admin/AdminSync'
import AdminConsultas from './pages/admin/AdminConsultas'
import AdminVuelos from './pages/admin/AdminVuelos'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          {/* ── Vista Cliente ── */}
          <Route path="/" element={<FlightSearch />} />
          <Route path="/vuelo/:id/asientos" element={<SeatSelection />} />
          <Route path="/ticket/:id" element={<TicketView />} />

          {/* Legacy routes — keep working */}
          <Route path="/flights/:id/seats" element={<SeatSelection />} />

          {/* ── Vista Administrador ── */}
          <Route path="/admin" element={<CompanyDashboard />} />
          <Route path="/admin/sync" element={<AdminSync />} />
          <Route path="/admin/consultas" element={<AdminConsultas />} />
          <Route path="/admin/vuelos" element={<AdminVuelos />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
