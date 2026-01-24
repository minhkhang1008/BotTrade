import React, { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle, Wifi, WifiOff } from 'lucide-react'
import useApi from '../hooks/useApi'

interface HealthStatus {
  status: string
  dnse_connected: boolean
  timestamp: string
  symbols: string[]
}

export default function ConnectionStatus() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const { get } = useApi()

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await get('/api/v1/health')
        setHealth(response.data)
      } catch (error) {
        console.error('Health check failed:', error)
      } finally {
        setLoading(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 10000) // Every 10 seconds

    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return <div className="animate-pulse bg-gray-700 px-3 py-2 rounded">...</div>
  }

  const isConnected = health?.status === 'ok'
  const dnseConnected = health?.dnse_connected

  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-gray-900 rounded">
      {isConnected ? (
        <CheckCircle className="w-4 h-4 text-green-500" />
      ) : (
        <AlertCircle className="w-4 h-4 text-red-500" />
      )}
      <span className="text-sm font-medium">Bot: {isConnected ? '🟢 OK' : '🔴 Error'}</span>

      {dnseConnected ? (
        <Wifi className="w-4 h-4 text-green-500" />
      ) : (
        <WifiOff className="w-4 h-4 text-yellow-500" />
      )}
      <span className="text-sm">DNSE: {dnseConnected ? '🟢 Connected' : '🟡 Disconnected'}</span>

      <span className="text-xs text-gray-400 ml-auto">
        {new Date(health?.timestamp || '').toLocaleTimeString()}
      </span>
    </div>
  )
}
