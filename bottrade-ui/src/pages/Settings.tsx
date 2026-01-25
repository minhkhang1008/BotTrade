import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import useAppStore from '../store/appStore'
import { Card } from '../components/Common/Card'
import { AlertCircle, Check, Plus, X, Play, Zap } from 'lucide-react'
import type { Signal } from '../types/api'

// Test signal for OTP flow testing
const TEST_SIGNAL: Signal = {
  id: 99999,
  symbol: 'VNM',
  signal_type: 'BUY',
  timestamp: new Date().toISOString(),
  entry: 78500,
  stop_loss: 76000,
  take_profit: 83500,
  quantity: 100,
  status: 'ACTIVE',
  reason: 'Test OTP Flow',
  risk: 2500,
  reward: 5000,
  risk_reward_ratio: 2.0
}

interface SettingsData {
  watchlist: string[]
  timeframe: string
  rsi_period: number
  macd_fast: number
  macd_slow: number
  macd_signal: number
  atr_period: number
  zone_width_atr_multiplier: number
  sl_buffer_atr_multiplier: number
  risk_reward_ratio: number
  default_quantity: number
}

const DEFAULT_SETTINGS: SettingsData = {
  watchlist: ['VNM', 'FPT', 'VIC', 'VHM', 'HPG'],
  timeframe: '1H',
  rsi_period: 14,
  macd_fast: 12,
  macd_slow: 26,
  macd_signal: 9,
  atr_period: 14,
  zone_width_atr_multiplier: 0.5,
  sl_buffer_atr_multiplier: 0.1,
  risk_reward_ratio: 2.0,
  default_quantity: 100
}

export default function SettingsPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formValues, setFormValues] = useState<SettingsData | null>(null)
  const [newSymbol, setNewSymbol] = useState('')
  const [showAddSymbol, setShowAddSymbol] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoMessage, setDemoMessage] = useState<string | null>(null)
  const [tradingStatus, setTradingStatus] = useState<{
    trading_enabled: boolean
    auto_trade_enabled: boolean
    trading_token_valid: boolean
    account_no: string
    mock_mode: boolean
    authenticated: boolean
    active_symbols: string[]
    signals_today: number
  } | null>(null)
  const { get, put, post } = useApi()
  
  // Global state
  const { demoMode, setDemoMode, autoTradeEnabled, setAutoTradeEnabled } = useAppStore()

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await get('/api/v1/settings')
        setSettings(response.data as SettingsData)
        setFormValues(response.data as SettingsData)
        setLoading(false)
      } catch (error) {
        console.error('Failed to fetch settings:', error)
        // Use default settings if API fails
        setSettings(DEFAULT_SETTINGS)
        setFormValues(DEFAULT_SETTINGS)
        setLoading(false)
      }
    }

    const fetchTradingStatus = async () => {
      try {
        const response = await get('/api/v1/trading/status')
        setTradingStatus(response.data)
        // Sync auto-trade state from server
        setAutoTradeEnabled(response.data.auto_trade_enabled)
      } catch (error) {
        console.error('Failed to fetch trading status:', error)
      }
    }

    fetchSettings()
    fetchTradingStatus()
  }, [])

  const handleChange = (field: keyof SettingsData, value: any) => {
    setFormValues(prev => prev ? { ...prev, [field]: value } : null)
    setSaved(false)
    setError(null)
  }

  const handleSave = async () => {
    if (!formValues) return
    
    setSaving(true)
    setError(null)
    try {
      await put('/api/v1/settings', formValues)
      setSettings(formValues)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error('Failed to save settings:', err)
      setError('Failed to save settings. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setFormValues(DEFAULT_SETTINGS)
    setSaved(false)
    setError(null)
  }

  const handleAddSymbol = () => {
    if (!formValues || !newSymbol.trim()) return
    
    const symbol = newSymbol.trim().toUpperCase()
    
    // Check if symbol already exists
    if (formValues.watchlist.includes(symbol)) {
      setError(`Symbol "${symbol}" already exists in watchlist`)
      return
    }
    
    handleChange('watchlist', [...formValues.watchlist, symbol])
    setNewSymbol('')
    setShowAddSymbol(false)
  }

  const handleRemoveSymbol = (index: number) => {
    if (!formValues) return
    handleChange('watchlist', formValues.watchlist.filter((_, i) => i !== index))
  }

  if (loading || !formValues) {
    return <div className="text-center py-8 text-gray-400">Loading settings...</div>
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
        <p className="text-gray-400">Configure bot parameters and indicators</p>
      </div>

      {/* Save Alert */}
      {saved && (
        <div className="bg-green-900/30 border border-green-700 rounded p-3 flex items-center gap-2 text-green-400">
          <Check className="w-5 h-5" />
          Settings saved successfully!
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded p-3 flex items-center gap-2 text-red-400">
          <AlertCircle className="w-5 h-5" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto hover:text-red-300">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Indicator Settings */}
      <Card title="📊 Indicator Settings">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div>
            <label className="text-sm text-gray-400 block mb-2">RSI Period</label>
            <input
              type="number"
              min="7"
              max="30"
              value={formValues.rsi_period}
              onChange={e => handleChange('rsi_period', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
            <div className="text-xs text-gray-500 mt-1">Range: 7-30</div>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">MACD Fast</label>
            <input
              type="number"
              min="5"
              max="20"
              value={formValues.macd_fast}
              onChange={e => handleChange('macd_fast', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
            <div className="text-xs text-gray-500 mt-1">Range: 5-20</div>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">MACD Slow</label>
            <input
              type="number"
              min="20"
              max="50"
              value={formValues.macd_slow}
              onChange={e => handleChange('macd_slow', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
            <div className="text-xs text-gray-500 mt-1">Range: 20-50</div>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">MACD Signal</label>
            <input
              type="number"
              min="5"
              max="15"
              value={formValues.macd_signal}
              onChange={e => handleChange('macd_signal', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
            <div className="text-xs text-gray-500 mt-1">Range: 5-15</div>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">ATR Period</label>
            <input
              type="number"
              min="7"
              max="30"
              value={formValues.atr_period}
              onChange={e => handleChange('atr_period', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
            <div className="text-xs text-gray-500 mt-1">Range: 7-30</div>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">Timeframe</label>
            <select
              value={formValues.timeframe}
              onChange={e => handleChange('timeframe', e.target.value)}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            >
              <option value="1H">1 Hour</option>
              <option value="4H">4 Hours</option>
              <option value="1D">1 Day</option>
              <option value="1W">1 Week</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Trading Settings */}
      <Card title="💰 Trading Settings">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="text-sm text-gray-400 block mb-2">Default Quantity (per trade)</label>
            <input
              type="number"
              min="1"
              value={formValues.default_quantity}
              onChange={e => handleChange('default_quantity', parseInt(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">Risk/Reward Ratio</label>
            <input
              type="number"
              min="0.5"
              step="0.1"
              value={formValues.risk_reward_ratio}
              onChange={e => handleChange('risk_reward_ratio', parseFloat(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">Zone Width (ATR multiplier)</label>
            <input
              type="number"
              min="0.1"
              step="0.05"
              value={formValues.zone_width_atr_multiplier}
              onChange={e => handleChange('zone_width_atr_multiplier', parseFloat(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">Stop Loss Buffer (ATR multiplier)</label>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={formValues.sl_buffer_atr_multiplier}
              onChange={e => handleChange('sl_buffer_atr_multiplier', parseFloat(e.target.value))}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white"
            />
          </div>
        </div>
      </Card>

      {/* Watchlist */}
      <Card title="👁️ Watchlist">
        <div>
          <label className="text-sm text-gray-400 block mb-2">Symbols to Monitor</label>
          <div className="bg-gray-700 rounded p-3">
            <div className="flex flex-wrap gap-2">
              {formValues.watchlist.map((symbol, index) => (
                <div
                  key={symbol}
                  className="bg-green-900/30 border border-green-700 text-green-400 px-3 py-1 rounded text-sm flex items-center gap-2"
                >
                  {symbol}
                  <button
                    onClick={() => handleRemoveSymbol(index)}
                    className="ml-1 hover:text-red-400 transition"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
              {formValues.watchlist.length === 0 && (
                <span className="text-gray-500 text-sm">No symbols in watchlist</span>
              )}
            </div>
          </div>
          
          {/* Add Symbol Form */}
          {showAddSymbol ? (
            <div className="mt-3 flex gap-2">
              <input
                type="text"
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
                onKeyDown={(e) => e.key === 'Enter' && handleAddSymbol()}
                placeholder="Enter symbol (e.g., VNM)"
                className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-green-500"
                autoFocus
              />
              <button
                onClick={handleAddSymbol}
                disabled={!newSymbol.trim()}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white rounded transition"
              >
                Add
              </button>
              <button
                onClick={() => {
                  setShowAddSymbol(false)
                  setNewSymbol('')
                }}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-500 text-gray-300 rounded transition"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button 
              onClick={() => setShowAddSymbol(true)}
              className="mt-3 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Symbol
            </button>
          )}
        </div>
      </Card>

      {/* Demo Mode */}
      <Card title="🎬 Demo Mode">
        <div className="space-y-3">
          <p className="text-gray-400 text-sm">
            Kích hoạt Demo Mode để tạo dữ liệu giả lập và signal mẫu. 
            Chỉ hoạt động khi bot chạy ở chế độ mock (--mock flag).
          </p>
          
          {demoMessage && (
            <div className={`p-3 rounded text-sm ${
              demoMessage.includes('Error') || demoMessage.includes('không') || demoMessage.includes('❌')
                ? 'bg-red-900/30 border border-red-700 text-red-400'
                : 'bg-green-900/30 border border-green-700 text-green-400'
            }`}>
              {demoMessage}
            </div>
          )}
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <button
              onClick={async () => {
                setDemoLoading(true)
                setDemoMessage(null)
                try {
                  const response = await post('/api/v1/demo/start', {})
                  setDemoMode(true)  // Enable demo mode in global state
                  setDemoMessage('🎬 Demo đã bắt đầu! Kiểm tra Dashboard và Chart để xem signals.')
                  setTimeout(() => setDemoMessage(null), 15000)
                } catch (err: any) {
                  const errorMsg = err?.response?.data?.detail || 'Lỗi khi khởi động demo'
                  setDemoMessage(`❌ ${errorMsg}`)
                } finally {
                  setDemoLoading(false)
                }
              }}
              disabled={demoLoading}
              className="px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:cursor-not-allowed text-white rounded transition font-medium flex items-center justify-center gap-2"
            >
              {demoLoading ? (
                <>
                  <span className="animate-spin">⏳</span>
                  Đang tạo scenario...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  🎬 Demo Scenario
                </>
              )}
            </button>
            
            <button
              onClick={async () => {
                setDemoLoading(true)
                setDemoMessage(null)
                try {
                  const response = await post('/api/v1/demo/force-signal', {})
                  setDemoMessage('🔔 Signal đã được tạo! Kiểm tra Dashboard và Signals page.')
                  setTimeout(() => setDemoMessage(null), 10000)
                } catch (err: any) {
                  const errorMsg = err?.response?.data?.detail || 'Lỗi khi tạo signal'
                  setDemoMessage(`❌ ${errorMsg}`)
                } finally {
                  setDemoLoading(false)
                }
              }}
              disabled={demoLoading}
              className="px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:cursor-not-allowed text-white rounded transition font-medium flex items-center justify-center gap-2"
            >
              🔔 Force Signal (Instant)
            </button>
          </div>
          
          <p className="text-xs text-gray-500">
            <strong>Demo Scenario:</strong> Tạo ~30 nến uptrend + signal (~15s). <br/>
            <strong>Force Signal:</strong> Tạo signal ngay lập tức để test UI.
          </p>
          
          {/* Demo Mode Indicator */}
          {demoMode && (
            <div className="mt-4 flex items-center justify-between p-3 bg-purple-900/30 border border-purple-700 rounded">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full animate-pulse" />
                <span className="text-purple-300 font-medium">Demo Mode Active</span>
              </div>
              <button
                onClick={() => setDemoMode(false)}
                className="text-purple-400 hover:text-purple-300 text-sm underline"
              >
                Tắt Demo Mode
              </button>
            </div>
          )}
        </div>
      </Card>

      {/* Auto-Trade */}
      <Card title="⚡ Auto-Trade">
        <div className="space-y-4">
          <p className="text-gray-400 text-sm">
            Khi bật Auto-Trade, bot sẽ tự động đặt lệnh mua khi có signal phù hợp.
            {demoMode && (
              <span className="text-purple-400 ml-1">
                (Demo mode: chỉ giả lập, không đặt lệnh thật)
              </span>
            )}
          </p>
          
          {/* Auto-Trade Toggle */}
          <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg border border-gray-700">
            <div className="flex items-center gap-3">
              <Zap className={`w-6 h-6 ${autoTradeEnabled ? 'text-yellow-400' : 'text-gray-500'}`} />
              <div>
                <div className="text-white font-medium">Auto-Trade</div>
                <div className="text-gray-400 text-sm">
                  {autoTradeEnabled 
                    ? (demoMode ? '🎭 Giả lập đặt lệnh (Demo)' : '🔥 Đặt lệnh thật')
                    : 'Chỉ thông báo signal, không đặt lệnh'}
                </div>
              </div>
            </div>
            <button
              onClick={() => {
                setAutoTradeEnabled(!autoTradeEnabled)
                // TODO: Call API to sync with backend
              }}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                autoTradeEnabled ? 'bg-yellow-500' : 'bg-gray-600'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  autoTradeEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Trading Status */}
          {tradingStatus && (
            <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Trạng thái:</span>
                  <span className={`ml-2 font-medium ${tradingStatus.mock_mode ? 'text-purple-400' : 'text-green-400'}`}>
                    {tradingStatus.mock_mode ? '🎭 Mock Mode' : '🔴 Live Mode'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">Xác thực:</span>
                  <span className={`ml-2 font-medium ${tradingStatus.authenticated ? 'text-green-400' : 'text-red-400'}`}>
                    {tradingStatus.authenticated ? '✅ Đã đăng nhập' : '❌ Chưa đăng nhập'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">Symbols:</span>
                  <span className="ml-2 text-white">{tradingStatus.active_symbols?.length || 0} mã</span>
                </div>
                <div>
                  <span className="text-gray-400">Signals hôm nay:</span>
                  <span className="ml-2 text-white">{tradingStatus.signals_today || 0}</span>
                </div>
              </div>
            </div>
          )}
          
          {/* Warning for Live Mode */}
          {autoTradeEnabled && !demoMode && (
            <div className="p-3 bg-red-900/30 border border-red-700 rounded text-sm text-red-400">
              ⚠️ <strong>Cảnh báo:</strong> Auto-Trade đang BẬT ở chế độ Live. 
              Bot sẽ đặt lệnh THẬT khi có signal. Đảm bảo bạn đã cấu hình đúng risk management.
            </div>
          )}
          
          {/* Test OTP Flow Button */}
          <button
            onClick={() => {
              // Set test signal in global state and navigate
              useAppStore.getState().setTestOtpSignal(TEST_SIGNAL)
              navigate('/')
            }}
            className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition flex items-center justify-center gap-2"
          >
            🔐 Test OTP Flow
            <span className="text-xs text-blue-200">(Mở dialog đặt lệnh)</span>
          </button>
        </div>
      </Card>

      {/* Action Buttons */}
      <div className="flex gap-3 justify-end">
        <button 
          onClick={handleReset}
          className="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition"
        >
          Reset to Default
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 disabled:cursor-not-allowed text-white rounded transition font-medium flex items-center gap-2"
        >
          {saving ? (
            <>
              <span className="animate-spin">⏳</span>
              Saving...
            </>
          ) : (
            <>💾 Save Changes</>
          )}
        </button>
      </div>
    </div>
  )
}
