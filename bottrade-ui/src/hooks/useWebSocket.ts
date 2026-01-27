import { useEffect, useRef, ReactNode } from 'react'
import useAppStore from '../store/appStore'

interface WebSocketMessage {
  event: 'system' | 'bar_closed' | 'signal' | 'signal_check'
  data: any
}

// Single WebSocket URL - use environment variable or default
const WS_URL = (import.meta as any).env?.VITE_WS_URL || 'ws://127.0.0.1:8001/ws/v1/stream'

// Singleton WebSocket manager to prevent multiple connections
let globalWs: WebSocket | null = null
let connectionPromise: Promise<void> | null = null
let listeners: Set<(msg: WebSocketMessage) => void> = new Set()
let isConnecting = false

function connectWebSocket(): Promise<void> {
  if (globalWs?.readyState === WebSocket.OPEN) {
    return Promise.resolve()
  }

  if (connectionPromise && isConnecting) {
    return connectionPromise
  }

  isConnecting = true
  connectionPromise = new Promise((resolve, reject) => {
    try {
      console.log('[WS] Connecting to:', WS_URL)
      globalWs = new WebSocket(WS_URL)

      globalWs.onopen = () => {
        console.log('[WS] Connected')
        isConnecting = false
        resolve()
      }

      globalWs.onmessage = (event: MessageEvent) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          listeners.forEach(listener => listener(message))
        } catch (error) {
          console.error('[WS] Failed to parse message:', error)
        }
      }

      globalWs.onerror = (error: Event) => {
        console.error('[WS] Error:', error)
        isConnecting = false
      }

      globalWs.onclose = (ev: CloseEvent) => {
        console.log('[WS] Disconnected:', ev.code, ev.reason)
        globalWs = null
        isConnecting = false
        connectionPromise = null

        // Auto-reconnect after 3 seconds if not a clean close
        if (ev.code !== 1000) {
          setTimeout(() => {
            console.log('[WS] Attempting reconnect...')
            connectWebSocket()
          }, 3000)
        }
      }

      // Timeout after 5 seconds
      setTimeout(() => {
        if (isConnecting) {
          console.warn('[WS] Connection timeout')
          globalWs?.close()
          isConnecting = false
          reject(new Error('Connection timeout'))
        }
      }, 5000)

    } catch (error) {
      isConnecting = false
      reject(error)
    }
  })

  return connectionPromise
}

export function useWebSocket() {
  const storeRef = useRef(useAppStore.getState())
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true

    // Subscribe to store changes
    const unsubStore = useAppStore.subscribe(state => {
      storeRef.current = state
    })

    // Message handler
    const handleMessage = (message: WebSocketMessage) => {
      if (!mounted.current) return

      const store = storeRef.current
      switch (message.event) {
        case 'system':
          console.log('[WS] System:', message.data)
          break
        case 'bar_closed':
          store.addBar(message.data)
          break
        case 'signal_check':
          console.log('[WS] 📊 Signal Check:', message.data)
          store.setSignalCheck(message.data)
          break
        case 'signal':
          console.log('[WS] 🔔 NEW SIGNAL:', message.data)
          store.addSignal(message.data)
          // Show browser notification for new signals
          if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(`🔔 ${message.data.signal_type} Signal: ${message.data.symbol}`, {
              body: `Entry: ${message.data.entry?.toLocaleString()} | SL: ${message.data.stop_loss?.toLocaleString()} | TP: ${message.data.take_profit?.toLocaleString()}`,
              icon: '/favicon.ico'
            })
          }
          break
      }
    }

    // Register listener
    listeners.add(handleMessage)

    // Connect
    connectWebSocket()
      .then(() => {
        if (mounted.current) {
          useAppStore.getState().setConnected(true)
        }
      })
      .catch(() => {
        if (mounted.current) {
          useAppStore.getState().setConnected(false)
        }
      })

    return () => {
      mounted.current = false
      listeners.delete(handleMessage)
      unsubStore()

      // Only close if no more listeners
      if (listeners.size === 0 && globalWs) {
        globalWs.close(1000, 'Component unmounted')
        globalWs = null
      }
    }
  }, []) // Empty deps - run once

  return { connected: useAppStore(state => state.connected) }
}

export function WebSocketProvider({ children }: { children: ReactNode }): ReactNode {
  useWebSocket()
  return children
}
