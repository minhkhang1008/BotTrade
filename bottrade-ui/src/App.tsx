import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout/Layout'
import DashboardPage from './pages/Dashboard'
import ChartPage from './pages/Chart'
import SignalsPage from './pages/Signals'
import SettingsPage from './pages/Settings'
import { WebSocketProvider } from './hooks/useWebSocket'
import { UserProfile } from './components/UserProfile'
import './styles/globals.css'

function App() {
  return (
    <WebSocketProvider>
      <Router>
        <div className="absolute top-4 right-4 z-50">
          <UserProfile />
        </div>
        <Layout>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/chart/:symbol" element={<ChartPage />} />
            <Route path="/signals" element={<SignalsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Layout>
      </Router>
    </WebSocketProvider>
  )
}

export default App