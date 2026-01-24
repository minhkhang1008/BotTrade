import React from 'react'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface Signal {
  id: number
  symbol: string
  signal_type: 'BUY' | 'SELL'
  entry: number
  status: string
}

interface ActiveSignalsCardProps {
  signals: Signal[]
}

export default function ActiveSignalsCard({ signals }: ActiveSignalsCardProps) {
  const activeSignals = signals.filter(s => s.status === 'ACTIVE')
  const buySignals = activeSignals.filter(s => s.signal_type === 'BUY')
  const sellSignals = activeSignals.filter(s => s.signal_type === 'SELL')

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <h3 className="text-sm font-bold text-gray-400 mb-2">Total Active</h3>
        <p className="text-3xl font-bold text-white">{activeSignals.length}</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp className="w-4 h-4 text-green-500" />
          <h3 className="text-sm font-bold text-gray-400">Buy Signals</h3>
        </div>
        <p className="text-3xl font-bold text-green-400">{buySignals.length}</p>
      </div>
      
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-4">
        <div className="flex items-center gap-2 mb-2">
          <TrendingDown className="w-4 h-4 text-red-500" />
          <h3 className="text-sm font-bold text-gray-400">Sell Signals</h3>
        </div>
        <p className="text-3xl font-bold text-red-400">{sellSignals.length}</p>
      </div>
    </div>
  )
}
