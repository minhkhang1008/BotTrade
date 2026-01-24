import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Download, Share2, RefreshCw } from 'lucide-react'
import { Card } from '../components/Common/Card'
import { useApi } from '../hooks/useApi'
import useAppStore from '../store/appStore'
import type { Bar, Signal } from '../types/api'

export default function ChartPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const { get } = useApi()
  const { bars, signals, addBar } = useAppStore()

  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState('1H')

  useEffect(() => {
    const fetchBars = async () => {
      if (!symbol) return
      try {
        const response = await get(`/api/v1/bars?symbol=${symbol}&limit=100`)
        addBar(response.data[0]) // Add to store
        setLoading(false)
      } catch (error) {
        console.error('Failed to fetch bars:', error)
        setLoading(false)
      }
    }

    fetchBars()
    const interval = setInterval(fetchBars, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [symbol])

  if (!symbol) return <div>Invalid symbol</div>

  const symbolBars = bars.get(symbol) || []
  const symbolSignals = signals.filter(s => s.symbol === symbol)
  const activeSignal = symbolSignals.find(s => s.status === 'ACTIVE')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 hover:bg-gray-800 rounded transition"
          >
            <ArrowLeft className="w-5 h-5 text-gray-400" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-white">{symbol} Chart</h1>
            <p className="text-gray-400">Technical Analysis & Trading Signals</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="p-2 hover:bg-gray-800 rounded transition" title="Refresh">
            <RefreshCw className="w-5 h-5 text-gray-300" />
          </button>
          <button className="p-2 hover:bg-gray-800 rounded transition" title="Download">
            <Download className="w-5 h-5 text-gray-300" />
          </button>
          <button className="p-2 hover:bg-gray-800 rounded transition" title="Share">
            <Share2 className="w-5 h-5 text-gray-300" />
          </button>
        </div>
      </div>

      {/* Timeframe Selector */}
      <div className="flex gap-2">
        {['1H', '4H', '1D', '1W'].map(tf => (
          <button
            key={tf}
            onClick={() => setTimeframe(tf)}
            className={`px-4 py-2 rounded transition ${
              timeframe === tf
                ? 'bg-green-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Chart Area */}
        <div className="lg:col-span-3">
          <Card title="Candlestick Chart">
            <div className="bg-black rounded h-96 flex items-center justify-center">
              {loading ? (
                <div className="text-gray-400">Loading chart...</div>
              ) : (
                <div className="text-gray-400 text-center">
                  <p>TradingView Lightweight Charts Integration</p>
                  <p className="text-sm mt-2">Bars: {symbolBars.length}</p>
                </div>
              )}
            </div>
          </Card>

          {/* Indicators */}
          <div className="mt-4 grid grid-cols-3 gap-4">
            <Card title="RSI (14)">
              <div className="text-2xl font-bold text-blue-400">65.2</div>
              <div className="text-xs text-gray-400 mt-2">Approaching Overbought</div>
            </Card>
            <Card title="MACD">
              <div className="text-2xl font-bold text-green-400">+2.15</div>
              <div className="text-xs text-gray-400 mt-2">Bullish Signal</div>
            </Card>
            <Card title="ATR (14)">
              <div className="text-2xl font-bold text-yellow-400">850</div>
              <div className="text-xs text-gray-400 mt-2">Moderate Volatility</div>
            </Card>
          </div>
        </div>

        {/* Right Panel */}
        <div className="space-y-4">
          {/* Current Price */}
          <Card title="Current Price">
            <div className="space-y-2">
              <div className="text-3xl font-bold text-white">75,500</div>
              <div className="flex items-center gap-2">
                <span className="text-green-400">↑ +0.67%</span>
                <span className="text-xs text-gray-400">Today</span>
              </div>
            </div>
          </Card>

          {/* Active Signal */}
          {activeSignal && (
            <Card title="Active Signal">
              <div className="space-y-3">
                <div
                  className={`px-3 py-2 rounded text-center font-bold ${
                    activeSignal.signal_type === 'BUY'
                      ? 'bg-green-900/30 text-green-400 border border-green-700'
                      : 'bg-red-900/30 text-red-400 border border-red-700'
                  }`}
                >
                  {activeSignal.signal_type} Signal
                </div>
                <div className="text-xs space-y-1">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Entry:</span>
                    <span className="font-bold text-white">{activeSignal.entry}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">SL:</span>
                    <span className="font-bold text-red-400">{activeSignal.stop_loss}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">TP:</span>
                    <span className="font-bold text-green-400">{activeSignal.take_profit}</span>
                  </div>
                  <div className="h-px bg-gray-700 my-2" />
                  <div className="flex justify-between">
                    <span className="text-gray-400">Risk:</span>
                    <span className="font-bold">{activeSignal.risk}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Reward:</span>
                    <span className="font-bold">{activeSignal.reward}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">R:R:</span>
                    <span className="font-bold text-yellow-400">{activeSignal.risk_reward_ratio}x</span>
                  </div>
                </div>
                <div className="text-xs text-gray-400 mt-3 p-2 bg-gray-700/20 rounded">
                  {activeSignal.reason}
                </div>
              </div>
            </Card>
          )}

          {/* Market Stats */}
          <Card title="Market Stats">
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-400">High:</span>
                <span className="text-white font-bold">76,000</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Low:</span>
                <span className="text-white font-bold">74,500</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Volume:</span>
                <span className="text-white font-bold">2.5M</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Open:</span>
                <span className="text-white font-bold">75,000</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
