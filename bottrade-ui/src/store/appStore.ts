import { create } from 'zustand'
import type { Signal, Bar, Settings, SignalCheck } from '../types/api'

interface AppState {
  // UI State
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void

  // Connection State
  connected: boolean
  setConnected: (connected: boolean) => void

  // Demo Mode State
  demoMode: boolean
  setDemoMode: (demoMode: boolean) => void

  // Auto Trade State
  autoTradeEnabled: boolean
  setAutoTradeEnabled: (enabled: boolean) => void

  // OTP Test State
  testOtpSignal: Signal | null
  setTestOtpSignal: (signal: Signal | null) => void

  // Signal Check State (for demo visualization)
  signalChecks: Map<string, SignalCheck>
  setSignalCheck: (check: SignalCheck) => void
  clearSignalChecks: () => void

  // Data State
  signals: Signal[]
  setSignals: (signals: Signal[]) => void
  addSignal: (signal: Signal) => void

  bars: Map<string, Bar[]>
  setBars: (symbol: string, bars: Bar[]) => void
  addBar: (bar: Bar) => void

  settings: Settings | null
  setSettings: (settings: Settings) => void

  // UI Preferences
  theme: 'dark' | 'light'
  setTheme: (theme: 'dark' | 'light') => void

  selectedSymbol: string | null
  setSelectedSymbol: (symbol: string | null) => void
}

export const useAppStore = create<AppState>(set => ({
  // UI State
  sidebarOpen: true,
  setSidebarOpen: (open: boolean) => set({ sidebarOpen: open }),
  toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),

  // Connection State
  connected: false,
  setConnected: (connected: boolean) => set({ connected }),

  // Demo Mode State
  demoMode: false,
  setDemoMode: (demoMode: boolean) => set({ demoMode }),

  // Auto Trade State
  autoTradeEnabled: false,
  setAutoTradeEnabled: (enabled: boolean) => set({ autoTradeEnabled: enabled }),

  // OTP Test State
  testOtpSignal: null,
  setTestOtpSignal: (signal: Signal | null) => set({ testOtpSignal: signal }),

  // Signal Check State (for demo visualization)
  signalChecks: new Map(),
  setSignalCheck: (check: SignalCheck) =>
    set(state => {
      const newChecks = new Map(state.signalChecks)
      newChecks.set(check.symbol, check)
      return { signalChecks: newChecks }
    }),
  clearSignalChecks: () => set({ signalChecks: new Map() }),

  // Data State
  signals: [],
  setSignals: (signals: Signal[]) => set({ signals }),
  addSignal: (signal: Signal) =>
    set(state => ({
      signals: [signal, ...state.signals].slice(0, 100) // Keep last 100
    })),

  bars: new Map(),
  setBars: (symbol: string, bars: Bar[]) =>
    set(state => {
      const newBars = new Map(state.bars)
      newBars.set(symbol, bars)
      return { bars: newBars }
    }),
  addBar: (bar: Bar) =>
    set(state => {
      const newBars = new Map(state.bars)
      const existing = newBars.get(bar.symbol) || []
      // Remove last bar if it has same timestamp and add new one
      const filtered = existing.filter(b => b.timestamp !== bar.timestamp)
      newBars.set(bar.symbol, [...filtered, bar])
      return { bars: newBars }
    }),

  settings: null,
  setSettings: (settings: Settings) => set({ settings }),

  // UI Preferences
  theme: 'dark',
  setTheme: (theme: 'dark' | 'light') => set({ theme }),

  selectedSymbol: 'VNM',
  setSelectedSymbol: (symbol: string | null) => set({ selectedSymbol: symbol })
}))

export default useAppStore
