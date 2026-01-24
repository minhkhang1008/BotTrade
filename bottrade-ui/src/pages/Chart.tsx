import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Download, Share2, RefreshCw } from 'lucide-react'
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickData } from 'lightweight-charts'
import { Card } from '../components/Common/Card'
import { useApi } from '../hooks/useApi'
import useAppStore from '../store/appStore'
import type { Bar, Signal } from '../types/api'

export default function ChartPage() {
  const { symbol: urlSymbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const { get } = useApi()
  const { bars, signals, addBar, setBars } = useAppStore()

  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState('1H')
  const [symbols, setSymbols] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState(urlSymbol || 'VNM')
  
  // Chart refs
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)

  // Fetch available symbols
  useEffect(() => {
    const fetchSymbols = async () => {
      try {
        const response = await get('/api/v1/symbols')
        setSymbols(response.data)
      } catch (error) {
        console.error('Failed to fetch symbols:', error)
        setSymbols(['VNM', 'FPT', 'VIC', 'VHM', 'HPG']) // fallback
      }
    }
    fetchSymbols()
  }, [])

  // Fetch bars data
  useEffect(() => {
    const fetchBars = async () => {
      if (!selectedSymbol) return
      setLoading(true)
      try {
        const response = await get(`/api/v1/bars?symbol=${selectedSymbol}&limit=200`)
        if (response.data && response.data.length > 0) {
          setBars(selectedSymbol, response.data)
        }
      } catch (error) {
        console.error('Failed to fetch bars:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchBars()
    const interval = setInterval(fetchBars, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [selectedSymbol])

  // Initialize and update chart
  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0a0a0a' },
        textColor: '#d1d5db',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    })

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      wickUpColor: '#22c55e',
    })

    chartRef.current = chart
    candlestickSeriesRef.current = candlestickSeries

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  // Update chart data when bars change
  useEffect(() => {
    if (!candlestickSeriesRef.current) return
    
    const symbolBars = bars.get(selectedSymbol) || []
    if (symbolBars.length === 0) return

    const chartData: CandlestickData[] = symbolBars
      .map(bar => ({
        time: (new Date(bar.timestamp).getTime() / 1000) as any,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number))

    candlestickSeriesRef.current.setData(chartData)
    chartRef.current?.timeScale().fitContent()
  }, [bars, selectedSymbol])

  // Handle symbol change
  const handleSymbolChange = (newSymbol: string) => {
    setSelectedSymbol(newSymbol)
    navigate(`/chart/${newSymbol}`, { replace: true })
  }

  const symbolBars = bars.get(selectedSymbol) || []
  const symbolSignals = signals.filter(s => s.symbol === selectedSymbol)
  const activeSignal = symbolSignals.find(s => s.status === 'ACTIVE')
  
  // Get latest bar for price display
  const latestBar = symbolBars[symbolBars.length - 1]
  const prevBar = symbolBars[symbolBars.length - 2]
  const priceChange = latestBar && prevBar ? ((latestBar.close - prevBar.close) / prevBar.close * 100) : 0

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
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold text-white">{selectedSymbol} Chart</h1>
              {/* Symbol Dropdown */}
              <select
                value={selectedSymbol}
                onChange={(e) => handleSymbolChange(e.target.value)}
                className="bg-gray-800 text-white border border-gray-600 rounded px-3 py-1 text-sm focus:outline-none focus:border-green-500"
              >
                {symbols.map(sym => (
                  <option key={sym} value={sym}>{sym}</option>
                ))}
              </select>
            </div>
            <p className="text-gray-400">Technical Analysis & Trading Signals</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={() => window.location.reload()}
            className="p-2 hover:bg-gray-800 rounded transition" 
            title="Refresh"
          >
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
          <Card title={`${selectedSymbol} - ${timeframe} Candlestick Chart`}>
            <div className="bg-black rounded">
              {loading ? (
                <div className="h-96 flex items-center justify-center text-gray-400">
                  Loading chart...
                </div>
              ) : symbolBars.length === 0 ? (
                <div className="h-96 flex items-center justify-center text-gray-400">
                  No data available for {selectedSymbol}
                </div>
              ) : (
                <div ref={chartContainerRef} className="w-full" />
              )}
            </div>
            <div className="text-xs text-gray-500 mt-2">
              Loaded {symbolBars.length} bars
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
