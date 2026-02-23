import React, { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, Activity } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import useAppStore from '../store/appStore'
import ConnectionStatus from '../components/Common/ConnectionStatus'
import ActiveSignalsCard from '../components/Common/ActiveSignalsCard'
import SignalCheckCard from '../components/Common/SignalCheckCard'
import { Card, CardGrid } from '../components/Common/Card'
import type { Signal, HealthStatus } from '../types/api'

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [apiSignals, setApiSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const { get } = useApi()
  
  // Get realtime signals from WebSocket store
  const realtimeSignals = useAppStore(state => state.signals)
  
  // Merge API signals with realtime signals (realtime takes priority)
  const signals = React.useMemo(() => {
    // Create map of existing signal IDs for quick lookup
    const apiSignalIds = new Set(apiSignals.map(s => s.id))
    // Add realtime signals that aren't in API response yet
    const newRealtimeSignals = realtimeSignals.filter(s => !apiSignalIds.has(s.id))
    // Combine: new realtime signals first, then API signals
    return [...newRealtimeSignals, ...apiSignals]
  }, [apiSignals, realtimeSignals])
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [healthRes, signalsRes] = await Promise.all([
          get('/api/v1/health'),
          get('/api/v1/signals?limit=50')
        ])
        setHealth(healthRes.data)
        setApiSignals(signalsRes.data)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-24 bg-gray-800 rounded-lg animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-32 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  const activeSignals = signals.filter(s => s.status === 'ACTIVE')
  const buySignals = activeSignals.filter(s => s.signal_type === 'BUY')
  const sellSignals = activeSignals.filter(s => s.signal_type === 'SELL')
  const winningSignals = signals.filter(s => s.status === 'TP_HIT').length
  const losingSignals = signals.filter(s => s.status === 'SL_HIT').length
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-gray-400">Real-time trading signals & market status</p>
      </div>

      {/* Connection Status */}
      <ConnectionStatus />

      {/* Main Metrics Grid */}
      <CardGrid cols={3}>
        <Card title="Active Signals" className="!p-6">
          <div className="flex items-center gap-3">
            <Activity className="w-8 h-8 text-green-500" />
            <div>
              <div className="text-3xl font-bold text-white">{activeSignals.length}</div>
              <div className="text-xs text-gray-400">Currently active</div>
            </div>
          </div>
        </Card>

        <Card title="BUY Signals" className="!p-6">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-8 h-8 text-green-500" />
            <div>
              <div className="text-3xl font-bold text-green-400">{buySignals.length}</div>
              <div className="text-xs text-gray-400">Bullish signals</div>
            </div>
          </div>
        </Card>

        <Card title="SELL Signals" className="!p-6">
          <div className="flex items-center gap-3">
            <TrendingDown className="w-8 h-8 text-red-500" />
            <div>
              <div className="text-3xl font-bold text-red-400">{sellSignals.length}</div>
              <div className="text-xs text-gray-400">Bearish signals</div>
            </div>
          </div>
        </Card>
      </CardGrid>

      {/* Signal Analysis - Live visualization of signal checks */}
      <SignalCheckCard />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Signals */}
        <div className="lg:col-span-2">
          <Card title="Latest Active Signals">
            <div className="space-y-2">
              {activeSignals.slice(0, 5).map(signal => (
                <div
                  key={signal.id}
                  className="bg-gray-700/30 rounded p-3 border border-gray-600 hover:border-gray-500 transition cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{signal.symbol}</span>
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            signal.signal_type === 'BUY'
                              ? 'bg-green-900/50 text-green-400'
                              : 'bg-red-900/50 text-red-400'
                          }`}
                        >
                          {signal.signal_type}
                        </span>
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        Entry: {signal.entry.toLocaleString()} | SL: {signal.stop_loss.toLocaleString()} | TP:{' '}
                        {signal.take_profit.toLocaleString()}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-bold text-white">{signal.risk_reward_ratio}x</div>
                      <div className="text-xs text-gray-400">R:R Ratio</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Stats */}
        <div className="space-y-4">
          <Card title="Signal Statistics">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Total Signals</span>
                <span className="font-bold text-white text-lg">{signals.length}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Winning ✓</span>
                <span className="font-bold text-green-400 text-lg">{winningSignals}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Losing ✕</span>
                <span className="font-bold text-red-400 text-lg">{losingSignals}</span>
              </div>
              <div className="h-px bg-gray-700 my-2" />
              <div className="flex justify-between items-center">
                <span className="text-gray-400">Monitoring</span>
                <span className="font-bold text-blue-400 text-lg">{health?.symbols.length || 0}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

