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

export interface TradingStatus {
  trading_enabled: boolean
  auto_trade_enabled: boolean
  trading_token_valid: boolean
  account_no: string
  mock_mode: boolean
  authenticated: boolean
  active_symbols: string[]
  signals_today: number
