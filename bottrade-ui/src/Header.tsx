import React from 'react'
import { Menu, Settings, LogOut } from 'lucide-react'
import useAppStore from '../../store/appStore'
import ConnectionStatus from '../Dashboard/ConnectionStatus'
import { useNavigate } from 'react-router-dom'

export default function Header() {
  const { toggleSidebar, theme, setTheme } = useAppStore()
  const navigate = useNavigate()

  return (
    <header className="sticky top-0 z-40 bg-gray-900 border-b border-gray-700">
      <div className="px-4 py-3 flex items-center justify-between">
        {/* Left Side */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="lg:hidden p-2 hover:bg-gray-800 rounded transition"
          >
            <Menu className="w-6 h-6 text-gray-300" />
          </button>

          <h1 className="text-2xl font-bold text-white">
            📈 <span className="text-green-400">Bot</span>Trade
          </h1>
        </div>

        {/* Center */}
        <div className="flex-1 px-8 hidden md:block">
          <ConnectionStatus />
        </div>

        {/* Right Side */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            className="p-2 hover:bg-gray-800 rounded transition"
            title="Toggle theme"
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>

          <button
            onClick={() => navigate('/settings')}
            className="p-2 hover:bg-gray-800 rounded transition"
            title="Settings"
          >
            <Settings className="w-5 h-5 text-gray-300" />
          </button>

          <button
            onClick={() => {
              // Logout logic
              navigate('/')
            }}
            className="p-2 hover:bg-gray-800 rounded transition"
            title="Logout"
          >
            <LogOut className="w-5 h-5 text-gray-300" />
          </button>
        </div>
      </div>
    </header>
  )
}
