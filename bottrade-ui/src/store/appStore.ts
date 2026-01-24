import { create } from 'zustand'
import type { Signal, Bar, Settings } from '../types/api'

interface AppState {
  // UI State
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void

  // Connection State
  connected: boolean
  setConnected: (connected: boolean) => void

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
