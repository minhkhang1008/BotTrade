import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { BarChart3, TrendingUp, Settings, LineChart, AlertCircle, X } from 'lucide-react'
import useAppStore from '../../store/appStore'
import { useMedia } from 'react-use'

const navigation = [
  { name: 'Dashboard', href: '/', icon: BarChart3 },
  { name: 'Chart', href: '/chart/VNM', icon: TrendingUp },
  { name: 'Signals', href: '/signals', icon: AlertCircle },
  { name: 'Analytics', href: '/analytics', icon: LineChart },
  { name: 'Settings', href: '/settings', icon: Settings }
]

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useAppStore()
  const navigate = useNavigate()
  const location = useLocation()
  const isMobile = !useMedia('(min-width: 1024px)', false)

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
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
            <p>🟢 Bot Running</p>
            <p>📊 5 Active Signals</p>
            <p>💰 +1.2% Today</p>
          </div>
        </div>
      </aside>
    </>
  )
}
