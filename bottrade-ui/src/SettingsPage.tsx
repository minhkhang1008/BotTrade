import React, { useEffect, useState } from 'react'
import useApi from '../../hooks/useApi'
import { Card } from '../Common/Card'
import { AlertCircle, Check } from 'lucide-react'

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

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saved, setSaved] = useState(false)
  const [formValues, setFormValues] = useState<SettingsData | null>(null)
  const { get, post } = useApi()

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await get('/api/v1/settings')
        setSettings(response.data)
        setFormValues(response.data)
        setLoading(false)
      } catch (error) {
        console.error('Failed to fetch settings:', error)
        setLoading(false)
      }
    }

    fetchSettings()
  }, [])

  const handleChange = (field: keyof SettingsData, value: any) => {
    setFormValues(prev => prev ? { ...prev, [field]: value } : null)
    setSaved(false)
  }

  const handleSave = async () => {
    try {
      await post('/api/v1/settings', formValues)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (error) {
      console.error('Failed to save settings:', error)
    }
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
                    onClick={() =>
                      handleChange(
                        'watchlist',
                        formValues.watchlist.filter((_, i) => i !== index)
                      )
                    }
                    className="ml-1 hover:text-red-400 transition"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
          <button className="mt-3 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition">
            + Add Symbol
          </button>
        </div>
      </Card>

      {/* Action Buttons */}
      <div className="flex gap-3 justify-end">
        <button className="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition">
          Reset to Default
        </button>
        <button
          onClick={handleSave}
          className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded transition font-medium"
        >
          💾 Save Changes
        </button>
      </div>
    </div>
  )
}
