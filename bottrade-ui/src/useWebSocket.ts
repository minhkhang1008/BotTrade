import { useEffect, useCallback, useRef, createContext, useContext, ReactNode } from 'react'
import useAppStore from '../store/appStore'

interface WebSocketMessage {
  event: 'system' | 'bar_closed' | 'signal'
  data: any
}

const WS_URL = (import.meta as any).env?.VITE_WS_URL || 'ws://localhost:8000/ws/v1/stream'

const WebSocketContext = createContext<null>(null)

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const store = useAppStore()
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  const connect = useCallback(() => {
    try {
      ws.current = new WebSocket(WS_URL)

      ws.current.onopen = () => {
        console.log('WebSocket connected')
        store.setConnected(true)
        reconnectAttempts.current = 0
      }

      ws.current.onmessage = (event: MessageEvent) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)

          switch (message.event) {
            case 'system':
              console.log('System event:', message.data)
              break

            case 'bar_closed':
              console.log('New bar:', message.data)
              store.addBar(message.data)
              break

            case 'signal':
              console.log('New signal:', message.data)
              store.addSignal(message.data)
              // Show notification here
              break

            default:
              console.log('Unknown event:', message.event)
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error)
        }
      }

      ws.current.onerror = (error: Event) => {
        console.error('WebSocket error:', error)
        store.setConnected(false)
      }

      ws.current.onclose = () => {
        console.log('WebSocket disconnected')
        store.setConnected(false)

        // Reconnect logic
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          console.log(`Attempting to reconnect in ${delay}ms...`)
          setTimeout(() => connect(), delay)
        }
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
    }
  }, [store])

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close()
      ws.current = null
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return { connected: store.connected }
}

export function WebSocketProvider({ children }: { children: ReactNode }) {
  useWebSocket()
  return <>{children}</>
}

export const useWebSocketContext = () => {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider')
  }
  return context
}
