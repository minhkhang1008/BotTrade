import React, { useEffect, useState } from 'react'
import useApi from '../hooks/useApi'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface Signal {
  id: number
  symbol: string
  signal_type: 'BUY' | 'SELL'
  entry: number
  stop_loss: number
  take_profit: number
  status: 'ACTIVE' | 'TP_HIT' | 'SL_HIT' | 'CANCELLED' | 'BREAKEVEN'
  timestamp: string
}

export default function ActiveSignalsCard() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)
  const { get } = useApi()

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const response = await get('/api/v1/signals?limit=10')
        setSignals(response.data.filter((s: Signal) => s.status === 'ACTIVE'))
      } catch (error) {
        console.error('Failed to fetch signals:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchSignals()
    const interval = setInterval(fetchSignals, 30000) // Every 30 seconds

    return () => clearInterval(interval)
  }, [])

  const buyCount = signals.filter(s => s.signal_type === 'BUY').length
  const sellCount = signals.filter(s => s.signal_type === 'SELL').length

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <h3 className="text-lg font-bold text-white mb-4">Active Signals</h3>

      {loading ? (
        <div className="animate-pulse space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-8 bg-gray-700 rounded"></div>
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-green-900/30 rounded p-3 border border-green-700">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-500" />
                <div>
                  <div className="text-xs text-gray-400">BUY Signals</div>
                  <div className="text-2xl font-bold text-green-400">{buyCount}</div>
                </div>
              </div>
            </div>

            <div className="bg-red-900/30 rounded p-3 border border-red-700">
              <div className="flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-red-500" />
                <div>
                  <div className="text-xs text-gray-400">SELL Signals</div>
                  <div className="text-2xl font-bold text-red-400">{sellCount}</div>
                </div>
              </div>
            </div>
          </div>

          {signals.length > 0 && (
            <div className="text-xs text-gray-400 mt-3">
              Showing {signals.length} active signal(s)
            </div>
          )}
        </div>
      )}
    </div>
  )
}
