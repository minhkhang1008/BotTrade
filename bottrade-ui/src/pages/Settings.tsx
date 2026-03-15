import React, { useEffect, useState } from 'react'
import { supabase } from '../supabase'
import { useApi } from '../hooks/useApi'
import useAppStore from '../store/appStore'
import { Card } from '../components/Common/Card'
import { AlertCircle, Check, Plus, X, Play } from 'lucide-react'

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

// Cấu hình mặc định nếu user mới tinh chưa có gì
const DEFAULT_SETTINGS: SettingsData = {
  watchlist: ['VNM', 'FPT', 'VIC', 'VHM', 'HPG'],
  timeframe: '1H',
  rsi_period: 14,
  macd_fast: 12,
  macd_slow: 26,
  macd_signal: 9,
  atr_period: 14,
  zone_width_atr_multiplier: 1.5,
  sl_buffer_atr_multiplier: 0.5,
  risk_reward_ratio: 2.0,
  default_quantity: 100
}

export default function Settings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [formValues, setFormValues] = useState<SettingsData | null>(null)
  const [userId, setUserId] = useState<string | null>(null)
  
  // State for Watchlist UI
  const [newSymbol, setNewSymbol] = useState('')
  const [showAddSymbol, setShowAddSymbol] = useState(false)
  
  // State for Demo Mode
  const [demoLoading, setDemoLoading] = useState(false)
  const [demoMessage, setDemoMessage] = useState<string | null>(null)
  const { post } = useApi()
  const { demoMode, setDemoMode } = useAppStore()

  useEffect(() => {
    const fetchSettings = async () => {
      // 1. Kiểm tra ai đang đăng nhập
      const { data: { session } } = await supabase.auth.getSession()
      
      if (!session) {
        setLoading(false)
        return // Nếu chưa đăng nhập thì thôi
      }
      
      const uid = session.user.id
      setUserId(uid)

      // 2. Lấy cấu hình riêng của user đó từ Supabase
      const { data, error: fetchError } = await supabase
        .from('user_settings')
        .select('config')
        .eq('user_id', uid)
        .single()

      if (fetchError) {
        console.error("Lỗi Supabase báo về:", fetchError)
      }

      if (data && data.config) {
        // Trộn cấu hình trên DB với cấu hình mặc định (phòng trường hợp thiếu key)
        setFormValues({ ...DEFAULT_SETTINGS, ...data.config })
      } else {
        setFormValues(DEFAULT_SETTINGS)
      }
      
      setLoading(false)
    }

    fetchSettings()
  }, [])

  const handleChange = (field: keyof SettingsData, value: any) => {
    setFormValues(prev => prev ? { ...prev, [field]: value } : null)
    setSaved(false)
    setError(null)
  }

  const handleAddSymbol = () => {
    if (!formValues || !newSymbol.trim()) return
    
    const symbol = newSymbol.trim().toUpperCase()
    
    // Check if symbol already exists
    if (formValues.watchlist.includes(symbol)) {
      setError(`Mã "${symbol}" đã có trong Watchlist`)
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

  const handleSave = async () => {
    if (!userId || !formValues) return

    setSaving(true)
    setError(null)

    try {
      // Upsert: Cập nhật hoặc thêm mới cấu hình vào DB
      const { error: saveError } = await supabase
        .from('user_settings')
        .upsert({ 
          user_id: userId, 
          config: formValues 
        }, { onConflict: 'user_id' })

      if (saveError) throw saveError

      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err: any) {
      console.error('Failed to save settings:', err)
      setError(err.message || 'Lỗi khi lưu cấu hình!')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    setFormValues(DEFAULT_SETTINGS)
    setSaved(false)
    setError(null)
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-400">Loading settings...</div>
  }

  if (!userId) {
    return (
      <div className="text-center py-8 text-yellow-400">
        ⚠️ Vui lòng Đăng nhập bằng Google ở góc trên cùng để sử dụng tính năng Settings!
      </div>
    )
  }

  if (!formValues) return null;

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
          Đã lưu cấu hình thành công!
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
            <input type="number" min="7" max="30" value={formValues.rsi_period} onChange={e => handleChange('rsi_period', parseInt(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">MACD Fast</label>
            <input type="number" min="5" max="20" value={formValues.macd_fast} onChange={e => handleChange('macd_fast', parseInt(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">MACD Slow</label>
            <input type="number" min="20" max="50" value={formValues.macd_slow} onChange={e => handleChange('macd_slow', parseInt(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">MACD Signal</label>
            <input type="number" min="5" max="15" value={formValues.macd_signal} onChange={e => handleChange('macd_signal', parseInt(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">ATR Period</label>
            <input type="number" min="7" max="30" value={formValues.atr_period} onChange={e => handleChange('atr_period', parseInt(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">Timeframe</label>
            <select value={formValues.timeframe} onChange={e => handleChange('timeframe', e.target.value)} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white">
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
            <input type="number" min="1" value={formValues.default_quantity} onChange={e => handleChange('default_quantity', parseInt(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">Risk/Reward Ratio</label>
            <input type="number" min="0.5" step="0.1" value={formValues.risk_reward_ratio} onChange={e => handleChange('risk_reward_ratio', parseFloat(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">Zone Width (ATR multiplier)</label>
            <input type="number" min="0.1" step="0.05" value={formValues.zone_width_atr_multiplier} onChange={e => handleChange('zone_width_atr_multiplier', parseFloat(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-2">Stop Loss Buffer (ATR multiplier)</label>
            <input type="number" min="0.01" step="0.01" value={formValues.sl_buffer_atr_multiplier} onChange={e => handleChange('sl_buffer_atr_multiplier', parseFloat(e.target.value))} className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white" />
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
                <div key={symbol} className="bg-green-900/30 border border-green-700 text-green-400 px-3 py-1 rounded text-sm flex items-center gap-2">
                  {symbol}
                  <button onClick={() => handleRemoveSymbol(index)} className="ml-1 hover:text-red-400 transition">
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
              <button onClick={handleAddSymbol} disabled={!newSymbol.trim()} className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white rounded transition">
                Add
              </button>
              <button onClick={() => { setShowAddSymbol(false); setNewSymbol('') }} className="px-4 py-2 bg-gray-600 hover:bg-gray-500 text-gray-300 rounded transition">
                Cancel
              </button>
            </div>
          ) : (
            <button onClick={() => setShowAddSymbol(true)} className="mt-3 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition flex items-center gap-2">
              <Plus className="w-4 h-4" /> Add Symbol
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
                  await post('/api/v1/demo/start', {})
                  setDemoMode(true)
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
              className="px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 text-white rounded transition font-medium flex items-center justify-center gap-2"
            >
              {demoLoading ? <>⏳ Đang tạo scenario...</> : <><Play className="w-5 h-5" /> 🎬 Demo Scenario</>}
            </button>
            
            <button
              onClick={async () => {
                setDemoLoading(true)
                setDemoMessage(null)
                try {
                  await post('/api/v1/demo/force-signal', {})
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
              className="px-6 py-3 bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white rounded transition font-medium flex items-center justify-center gap-2"
            >
              🔔 Force Signal (Instant)
            </button>
          </div>
          
          {demoMode && (
            <div className="mt-4 flex items-center justify-between p-3 bg-purple-900/30 border border-purple-700 rounded">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full animate-pulse" />
                <span className="text-purple-300 font-medium">Demo Mode Active</span>
              </div>
              <button onClick={() => setDemoMode(false)} className="text-purple-400 hover:text-purple-300 text-sm underline">
                Tắt Demo Mode
              </button>
            </div>
          )}
        </div>
      </Card>

      {/* Action Buttons */}
      <div className="flex gap-3 justify-end">
        <button onClick={handleReset} className="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition">
          Reset to Default
        </button>
        <button onClick={handleSave} disabled={saving} className="px-6 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white rounded transition font-medium flex items-center gap-2">
          {saving ? <>⏳ Saving...</> : <>💾 Save Changes</>}
        </button>
      </div>
    </div>
  )
}