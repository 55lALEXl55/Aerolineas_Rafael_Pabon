import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import FlightSearch from './pages/FlightSearch'
import SeatSelection from './pages/SeatSelection'
import FlightDashboard from './pages/FlightDashboard'
import CompanyDashboard from './pages/CompanyDashboard'
import QueryPanel from './pages/QueryPanel'
import TicketView from './pages/TicketView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<FlightSearch />} />
          <Route path="/flights/:id/seats" element={<SeatSelection />} />
          <Route path="/flights/:id/dashboard" element={<FlightDashboard />} />
          <Route path="/dashboard" element={<CompanyDashboard />} />
          <Route path="/queries" element={<QueryPanel />} />
          <Route path="/ticket/:id" element={<TicketView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
