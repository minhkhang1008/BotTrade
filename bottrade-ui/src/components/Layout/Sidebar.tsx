import React, { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { BarChart3, TrendingUp, Settings, LineChart, AlertCircle, X } from 'lucide-react'
import useAppStore from '../../store/appStore'
import { useMedia } from 'react-use'
import { useApi } from '../../hooks/useApi'

interface HealthStatus {
  status: string
  dnse_connected: boolean
  timestamp: string
  symbols: string[]
}

interface SettingsData {
  watchlist: string[]
}

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar, signals } = useAppStore()
  const navigate = useNavigate()
  const location = useLocation()
  const isMobile = !useMedia('(min-width: 1024px)', false)
  const { get } = useApi()
  
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [firstSymbol, setFirstSymbol] = useState('VNM')

  // Fetch health status
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await get('/api/v1/health')
        setHealth(response.data as HealthStatus)
      } catch (error) {
        setHealth(null)
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  // Fetch settings to get first symbol from watchlist - refresh when location changes
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await get('/api/v1/settings')
        const settings = response.data as SettingsData
        if (settings.watchlist && settings.watchlist.length > 0) {
          setFirstSymbol(settings.watchlist[0])
        }
      } catch (error) {
        // Keep default VNM
      }
    }
    fetchSettings()
    // Also refresh periodically to catch updates
    const interval = setInterval(fetchSettings, 5000)
    return () => clearInterval(interval)
  }, [location.pathname])

  // Build navigation with dynamic chart URL
  const navigation = [
    { name: 'Dashboard', href: '/', icon: BarChart3 },
    { name: 'Chart', href: `/chart/${firstSymbol}`, icon: TrendingUp },
    { name: 'Signals', href: '/signals', icon: AlertCircle },
    { name: 'Analytics', href: '/analytics', icon: LineChart },
    { name: 'Settings', href: '/settings', icon: Settings }
  ]

  // Calculate active signals count
  const activeSignalsCount = signals.filter(s => s.status === 'ACTIVE').length

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
    if (href.startsWith('/chart/')) return location.pathname.startsWith('/chart/')
    return location.pathname.startsWith(href)
  }

  const handleNavigate = (href: string) => {
    navigate(href)
    if (isMobile) toggleSidebar()
  }

  return (
    <>
      {/* Mobile overlay */}
      {isMobile && sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-16 h-[calc(100vh-4rem)] w-64 bg-gray-900 border-r border-gray-700 transition-transform z-40 lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Close button on mobile */}
        {isMobile && (
          <button
            onClick={toggleSidebar}
            className="absolute top-4 right-4 p-2 hover:bg-gray-800 rounded"
          >
            <X className="w-5 h-5 text-gray-300" />
          </button>
        )}

        <nav className="p-4 space-y-2">
          {navigation.map(item => {
            const Icon = item.icon
            const active = isActive(item.href)

            return (
              <button
                key={item.href}
                onClick={() => handleNavigate(item.href)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                  active
                    ? 'bg-green-900/30 text-green-400 border border-green-700'
                    : 'text-gray-400 hover:bg-gray-800'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium">{item.name}</span>
              </button>
            )
          })}
        </nav>

        {/* Bottom info */}
        <div className="absolute bottom-4 left-4 right-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
          <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-2">
            Quick Info
          </h4>
          <div className="space-y-1 text-xs text-gray-400">
            <p>{health?.status === 'ok' ? '🟢' : '🔴'} Bot {health?.status === 'ok' ? 'Running' : 'Error'}</p>
            <p>📊 {activeSignalsCount} Active Signal{activeSignalsCount !== 1 ? 's' : ''}</p>
            <p>🔗 DNSE {health?.dnse_connected ? 'Connected' : 'Disconnected'}</p>
          </div>
        </div>
      </aside>
    </>
  )
}
