// API Response Types
export interface Signal {
  id: number
  symbol: string
  signal_type: 'BUY' | 'SELL'
  timestamp: string
  entry: number
  stop_loss: number
  take_profit: number
  quantity: number
  status: 'ACTIVE' | 'TP_HIT' | 'SL_HIT' | 'CANCELLED' | 'BREAKEVEN'
  reason: string
  risk: number
  reward: number
  risk_reward_ratio: number
}

export interface Bar {
  symbol: string
  timeframe: string
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface HealthStatus {
  status: 'ok' | 'error'
  dnse_connected: boolean
  timestamp: string
  symbols: string[]
}

export interface Settings {
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

// Pivot point for analysis
export interface PivotPoint {
  price: number
  index: number
}

// Support zone info
export interface SupportZone {
  pivot_price: number
  zone_low: number
  zone_high: number
}

// Analysis details for signal check
export interface AnalysisDetails {
  pivot_lows: PivotPoint[]
  pivot_highs: PivotPoint[]
  pivot_lows_count: number
  pivot_highs_count: number
  // Trend analysis results (consecutive higher pairs)
  higher_lows_count?: number
  higher_highs_count?: number
  is_uptrend?: boolean
  trend_reason?: string
  support_zone: SupportZone | null
  bar_low: number
  bar_high: number
  total_bars: number
}

// Signal Check Progress (for demo visualization)
export interface SignalCheck {
  symbol: string
  bar: Bar
  conditions_passed: number
  total_conditions: number
  passed: string[]
  failed: string[]
  indicators: {
    rsi?: number | null
    macd?: number | null
    macd_signal?: number | null
    atr?: number | null
  }
  analysis?: AnalysisDetails
  timestamp: string
}
