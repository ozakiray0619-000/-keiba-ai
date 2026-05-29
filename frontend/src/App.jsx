import { Routes, Route } from 'react-router-dom'
import RaceListPage from './pages/RaceListPage'
import RaceDetailPage from './pages/RaceDetailPage'
import Header from './components/Header'

export default function App() {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="container mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<RaceListPage />} />
          <Route path="/race/:id" element={<RaceDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}
