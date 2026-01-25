import React, { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Download, Share2, RefreshCw } from 'lucide-react'
import { Card } from '../components/Common/Card'
import { useApi } from '../hooks/useApi'
import useAppStore from '../store/appStore'
import type { Signal } from '../types/api'

// Simplize Widget Configuration Interface
interface SimplizeWidgetConfig {
  tickers: { ticker: string; type: string }[]
  default_time_frame: string
  time_frames: string[]
  theme: 'light' | 'dark'
  auto_size: boolean
  font: string
  text_color: string
  text_color_chart: string
  background_color: string
  tab_colors: { active: string; default: string }
  chart_height: number
  show_price_chart: boolean
  show_fi: boolean
  chart_type: 'candle' | 'line'
  chart_line_color: string
  chart_candle_color: [string, string]
  fi: string[]
}

// Simplize Widget Component
interface SimplizeWidgetProps {
  tickers: string[]
  defaultTimeFrame?: string
  theme?: 'light' | 'dark'
  chartType?: 'candle' | 'line'
  chartHeight?: number
}

function SimplizeWidget({ 
  tickers, 
  defaultTimeFrame = 'all',
  theme = 'dark',
  chartType = 'candle',
  chartHeight = 400
}: SimplizeWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    // Clear previous widget
    containerRef.current.innerHTML = ''

    // Create widget container
    const widgetContainer = document.createElement('div')
    widgetContainer.className = 'simplize-widget-chart-overview'

    // Build widget configuration
    const config: SimplizeWidgetConfig = {
      tickers: tickers.map(ticker => ({ ticker, type: 'stock' })),
      default_time_frame: defaultTimeFrame,
      time_frames: ['all', '1D', '1W', '1M', '3M', '1Y'],
      theme: theme,
      auto_size: true,
      font: 'Inter',
      text_color: theme === 'dark' ? '#E5E7EB' : '#22313F',
      text_color_chart: theme === 'dark' ? '#E5E7EB' : '#22313F',
      background_color: theme === 'dark' ? '#1F2937' : '#FFFFFF',
      tab_colors: {
        active: '#006CEC',
        default: theme === 'dark' ? '#374151' : '#F2F2F2'
      },
      chart_height: chartHeight,
      show_price_chart: true,
      show_fi: true,
      chart_type: chartType,
      chart_line_color: '#EC8000',
      chart_candle_color: ['#25B770', '#E14040'],
      fi: ['market_cap_vnd', 'volume', 'outstanding_shares', 'pe_ratio', 'pb_ratio', 'eps'],
      size: { width: '', height: '' }
    } as SimplizeWidgetConfig & { size: { width: string; height: string } }

    // Create script
    const script = document.createElement('script')
    script.type = 'text/javascript'
    script.src = 'https://static.simplize.vn/static/widget/simplize-widget-v0.0.2.min.js'
    script.async = true
    script.innerHTML = JSON.stringify(config)

    widgetContainer.appendChild(script)
    containerRef.current.appendChild(widgetContainer)

    // Cleanup function
    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = ''
      }
    }
  }, [tickers, defaultTimeFrame, theme, chartType, chartHeight])

  return <div ref={containerRef} className="w-full h-full" style={{ minHeight: `${chartHeight + 200}px` }} />
}

// Interface for bar data
interface BarData {
  symbol: string
  timeframe: string
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

// Interface for indicator data
interface IndicatorData {
  symbol: string
  rsi: number | null
  macd_line: number | null
  macd_signal: number | null
  macd_histogram: number | null
  atr: number | null
  has_macd_crossover: boolean
  timestamp: string
}

// Interface for settings data
interface SettingsData {
  rsi_period: number
  macd_fast: number
  macd_slow: number
  macd_signal: number
  atr_period: number
}

export default function ChartPage() {
  const { symbol: urlSymbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const { get } = useApi()
  const { signals, demoMode, bars: wsBars } = useAppStore()

  const [chartType, setChartType] = useState<'candle' | 'line'>('candle')
  const [symbols, setSymbols] = useState<string[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState(urlSymbol || 'VNM')
  const [marketData, setMarketData] = useState<{
    currentPrice: number
    priceChange: number
    priceChangePercent: number
    high: number
    low: number
    open: number
    volume: number
    timestamp: string
  } | null>(null)
  const [indicatorData, setIndicatorData] = useState<IndicatorData | null>(null)
  const [indicatorSettings, setIndicatorSettings] = useState<SettingsData | null>(null)
  const [loadingMarketData, setLoadingMarketData] = useState(true)
  const [lastFetchTime, setLastFetchTime] = useState<Date | null>(null)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const prevPriceRef = useRef<number | null>(null)
  const [priceFlash, setPriceFlash] = useState<'up' | 'down' | null>(null)

  // Sync selectedSymbol with URL parameter
  useEffect(() => {
    if (urlSymbol && urlSymbol !== selectedSymbol) {
      setSelectedSymbol(urlSymbol)
    }
  }, [urlSymbol])

  // Fetch available symbols
  useEffect(() => {
    const fetchSymbols = async () => {
      try {
        const response = await get('/api/v1/symbols')
        if (Array.isArray(response.data)) {
          setSymbols(response.data as string[])
        }
      } catch (error) {
        console.error('Failed to fetch symbols:', error)
        setSymbols(['VNM', 'FPT', 'VIC', 'VHM', 'HPG']) // fallback
      }
    }
    fetchSymbols()
  }, [])

  // Fetch market data for selected symbol
  useEffect(() => {
    const fetchMarketData = async () => {
      if (!selectedSymbol) return
      setLoadingMarketData(true)
      setFetchError(null)
      try {
        const response = await get(`/api/v1/bars?symbol=${selectedSymbol}&limit=2`)
        const bars = response.data as BarData[]
        setLastFetchTime(new Date())
        
        if (bars && bars.length > 0) {
          const latestBar = bars[bars.length - 1]
          const prevBar = bars.length > 1 ? bars[bars.length - 2] : null
          
          const priceChange = prevBar ? latestBar.close - prevBar.close : 0
          const priceChangePercent = prevBar ? ((latestBar.close - prevBar.close) / prevBar.close * 100) : 0
          
          setMarketData({
            currentPrice: latestBar.close,
            priceChange,
            priceChangePercent,
            high: latestBar.high,
            low: latestBar.low,
            open: latestBar.open,
            volume: latestBar.volume,
            timestamp: latestBar.timestamp
          })
        } else {
          setMarketData(null)
          setFetchError('Bot chưa thu thập dữ liệu cho mã này. Hãy đảm bảo bot đang chạy và mã nằm trong watchlist.')
        }
      } catch (error) {
        console.error('Failed to fetch market data:', error)
        setMarketData(null)
        setFetchError('Không thể kết nối API. Kiểm tra backend đang chạy.')
      } finally {
        setLoadingMarketData(false)
      }
    }

    fetchMarketData()
    const interval = setInterval(fetchMarketData, 15000) // Refresh every 15 seconds (faster)
    return () => clearInterval(interval)
  }, [selectedSymbol])

  // Listen to WebSocket bars for realtime price updates
  useEffect(() => {
    const symbolBars = wsBars.get(selectedSymbol)
    if (symbolBars && symbolBars.length > 0) {
      const latestBar = symbolBars[symbolBars.length - 1]
      const prevBar = symbolBars.length > 1 ? symbolBars[symbolBars.length - 2] : null
      
      const newPrice = latestBar.close
      const oldPrice = prevPriceRef.current
      
      // Flash animation when price changes
      if (oldPrice !== null && newPrice !== oldPrice) {
        setPriceFlash(newPrice > oldPrice ? 'up' : 'down')
        setTimeout(() => setPriceFlash(null), 500)
      }
      prevPriceRef.current = newPrice
      
      const priceChange = prevBar ? latestBar.close - prevBar.close : 0
      const priceChangePercent = prevBar ? ((latestBar.close - prevBar.close) / prevBar.close * 100) : 0
      
      setMarketData({
        currentPrice: latestBar.close,
        priceChange,
        priceChangePercent,
        high: latestBar.high,
        low: latestBar.low,
        open: latestBar.open,
        volume: latestBar.volume,
        timestamp: latestBar.timestamp
      })
      setLastFetchTime(new Date())
      setLoadingMarketData(false)
    }
  }, [wsBars, selectedSymbol])

  // Fetch indicator data and settings
  useEffect(() => {
    const fetchIndicators = async () => {
      if (!selectedSymbol) return
      try {
        // Fetch indicators
        const indicatorResponse = await get(`/api/v1/indicators/${selectedSymbol}`)
        setIndicatorData(indicatorResponse.data as IndicatorData)
        
        // Fetch settings for period display
        const settingsResponse = await get('/api/v1/settings')
        setIndicatorSettings(settingsResponse.data as SettingsData)
      } catch (error) {
        console.error('Failed to fetch indicators:', error)
      }
    }

    fetchIndicators()
    const interval = setInterval(fetchIndicators, 15000)
    return () => clearInterval(interval)
  }, [selectedSymbol])

  // Handle symbol change
  const handleSymbolChange = (newSymbol: string) => {
    setSelectedSymbol(newSymbol)
    navigate(`/chart/${newSymbol}`, { replace: true })
  }

  // Format number for display
  const formatNumber = (num: number, decimals: number = 0): string => {
    return num.toLocaleString('vi-VN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
  }

  // Format volume
  const formatVolume = (vol: number): string => {
    if (vol >= 1000000) return `${(vol / 1000000).toFixed(1)}M`
    if (vol >= 1000) return `${(vol / 1000).toFixed(1)}K`
    return vol.toString()
  }

  const symbolSignals = signals.filter(s => s.symbol === selectedSymbol)
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
          {/* Chart Type Toggle */}
          <div className="flex bg-gray-800 rounded overflow-hidden mr-2">
            <button
              onClick={() => setChartType('candle')}
              className={`px-3 py-2 text-sm transition ${
                chartType === 'candle' 
                  ? 'bg-green-600 text-white' 
                  : 'text-gray-300 hover:bg-gray-700'
              }`}
              title="Candlestick Chart"
            >
              Candle
            </button>
            <button
              onClick={() => setChartType('line')}
              className={`px-3 py-2 text-sm transition ${
                chartType === 'line' 
                  ? 'bg-green-600 text-white' 
                  : 'text-gray-300 hover:bg-gray-700'
              }`}
              title="Line Chart"
            >
              Line
            </button>
          </div>
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

      {/* Main Content */}
      <div className={`grid grid-cols-1 gap-6 ${demoMode ? 'lg:grid-cols-3' : 'lg:grid-cols-4'}`}>
        {/* Chart Area - Only show when NOT in demo mode */}
        {!demoMode && (
          <div className="lg:col-span-3">
            <Card title={`${selectedSymbol} - Simplize Chart`}>
              <div className="bg-gray-900 rounded overflow-hidden">
                <SimplizeWidget 
                  key={`${selectedSymbol}-${chartType}`}
                  tickers={[selectedSymbol]}
                  theme="dark"
                  chartType={chartType}
                  chartHeight={400}
                />
              </div>
            </Card>
          </div>
        )}

        {/* Info Panels - Full width when demo mode, sidebar when not */}
        <div className={`${demoMode ? 'lg:col-span-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-4'}`}>
          {/* Demo Mode Notice */}
          {demoMode && (
            <div className="md:col-span-2 lg:col-span-3 bg-purple-900/30 border border-purple-700 rounded-lg p-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🎬</span>
                <div>
                  <div className="font-bold text-purple-400">Demo Mode Active</div>
                  <div className="text-sm text-purple-300">Đang sử dụng dữ liệu mô phỏng. Biểu đồ Simplize bị tắt.</div>
                </div>
              </div>
            </div>
          )}

          {/* Current Price */}
          <Card title="Current Price">
            {loadingMarketData ? (
              <div className="animate-pulse space-y-2">
                <div className="h-8 bg-gray-700 rounded w-24"></div>
                <div className="h-4 bg-gray-700 rounded w-20"></div>
              </div>
            ) : marketData ? (
              <div className="space-y-2">
                <div className={`text-3xl font-bold transition-all duration-300 ${
                  priceFlash === 'up' ? 'text-green-400 scale-105' : 
                  priceFlash === 'down' ? 'text-red-400 scale-105' : 
                  'text-white'
                }`}>
                  {formatNumber(marketData.currentPrice, 1)}
                  {priceFlash && (
                    <span className="ml-2 text-lg">
                      {priceFlash === 'up' ? '↑' : '↓'}
                    </span>
                  )}
                </div>
                {lastFetchTime && (
                  <div className="text-xs text-gray-500">
                    Cập nhật: {lastFetchTime.toLocaleTimeString('vi-VN')}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-yellow-500 text-sm">⚠️ Chưa có dữ liệu</div>
                {fetchError && (
                  <div className="text-xs text-gray-400">{fetchError}</div>
                )}
              </div>
            )}
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
                    <span className="font-bold text-white">{formatNumber(activeSignal.entry, 1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">SL:</span>
                    <span className="font-bold text-red-400">{formatNumber(activeSignal.stop_loss, 1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">TP:</span>
                    <span className="font-bold text-green-400">{formatNumber(activeSignal.take_profit, 1)}</span>
                  </div>
                  <div className="h-px bg-gray-700 my-2" />
                  <div className="flex justify-between">
                    <span className="text-gray-400">Risk:</span>
                    <span className="font-bold">{formatNumber(activeSignal.risk, 1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Reward:</span>
                    <span className="font-bold">{formatNumber(activeSignal.reward, 1)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">R:R:</span>
                    <span className="font-bold text-yellow-400">{activeSignal.risk_reward_ratio.toFixed(1)}x</span>
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
            {loadingMarketData ? (
              <div className="animate-pulse space-y-2">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="flex justify-between">
                    <div className="h-3 bg-gray-700 rounded w-12"></div>
                    <div className="h-3 bg-gray-700 rounded w-16"></div>
                  </div>
                ))}
              </div>
            ) : marketData ? (
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-400">High:</span>
                  <span className="text-white font-bold">{formatNumber(marketData.high, 1)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Low:</span>
                  <span className="text-white font-bold">{formatNumber(marketData.low, 1)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Volume:</span>
                  <span className="text-white font-bold">{formatVolume(marketData.volume)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Open:</span>
                  <span className="text-white font-bold">{formatNumber(marketData.open, 1)}</span>
                </div>
                {marketData.timestamp && (
                  <div className="pt-2 border-t border-gray-700 mt-2">
                    <span className="text-gray-500">Bar time: {new Date(marketData.timestamp).toLocaleString('vi-VN')}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-yellow-500 text-sm">⚠️ Chưa có dữ liệu</div>
            )}
          </Card>

          {/* Technical Indicators */}
          <Card title="📊 Indicators">
            {indicatorData ? (
              <div className="space-y-3 text-xs">
                {/* RSI */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-gray-400">RSI ({indicatorSettings?.rsi_period || 14})</span>
                    <span className={`font-bold ${
                      indicatorData.rsi === null ? 'text-gray-500' :
                      indicatorData.rsi > 70 ? 'text-red-400' :
                      indicatorData.rsi < 30 ? 'text-green-400' :
                      'text-white'
                    }`}>
                      {indicatorData.rsi !== null ? indicatorData.rsi.toFixed(1) : 'N/A'}
                    </span>
                  </div>
                  {indicatorData.rsi !== null && (
                    <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${
                          indicatorData.rsi > 70 ? 'bg-red-500' :
                          indicatorData.rsi < 30 ? 'bg-green-500' :
                          'bg-blue-500'
                        }`}
                        style={{ width: `${indicatorData.rsi}%` }}
                      />
                    </div>
                  )}
                  <div className="flex justify-between text-[10px] text-gray-500 mt-0.5">
                    <span>Oversold &lt;30</span>
                    <span>&gt;70 Overbought</span>
                  </div>
                </div>

                <div className="h-px bg-gray-700" />

                {/* MACD */}
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-gray-400">
                      MACD ({indicatorSettings?.macd_fast || 12},{indicatorSettings?.macd_slow || 26},{indicatorSettings?.macd_signal || 9})
                    </span>
                    {indicatorData.has_macd_crossover && (
                      <span className="text-green-400 text-[10px] animate-pulse">🔥 CROSSOVER</span>
                    )}
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Line:</span>
                      <span className={`font-bold ${
                        indicatorData.macd_line === null ? 'text-gray-500' :
                        indicatorData.macd_line > 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {indicatorData.macd_line !== null ? indicatorData.macd_line.toFixed(2) : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Signal:</span>
                      <span className="font-bold text-yellow-400">
                        {indicatorData.macd_signal !== null ? indicatorData.macd_signal.toFixed(2) : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Histogram:</span>
                      <span className={`font-bold ${
                        indicatorData.macd_histogram === null ? 'text-gray-500' :
                        indicatorData.macd_histogram > 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {indicatorData.macd_histogram !== null ? indicatorData.macd_histogram.toFixed(2) : 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="h-px bg-gray-700" />

                {/* ATR */}
                <div className="flex justify-between items-center">
                  <span className="text-gray-400">ATR ({indicatorSettings?.atr_period || 14})</span>
                  <span className="font-bold text-white">
                    {indicatorData.atr !== null ? indicatorData.atr.toFixed(1) : 'N/A'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-gray-500 text-sm">Đang tải chỉ báo...</div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
