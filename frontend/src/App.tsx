import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { CallsPage } from './pages/CallsPage'
import { CallDetail } from './pages/CallDetail'
import { HubSpotDeals } from './pages/HubSpotDeals'
import { Analytics } from './pages/Analytics'
import { TestingPage } from './pages/TestingPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/calls" element={<CallsPage />} />
          <Route path="/calls/:callSid" element={<CallDetail />} />
          <Route path="/hubspot" element={<HubSpotDeals />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/testing" element={<TestingPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
