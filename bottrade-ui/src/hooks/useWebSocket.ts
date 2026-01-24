import { useEffect, useCallback, useRef, createContext, useContext, ReactNode } from 'react'
import useAppStore from '../store/appStore'

interface WebSocketMessage {
  event: 'system' | 'bar_closed' | 'signal'
  data: any
}


// Build a prioritized list of candidate WS endpoints to try. This helps
// when `localhost` resolves to IPv6 (::1) but the server is bound to IPv4.
const ENV_WS = (import.meta as any).env?.VITE_WS_URL
const WS_CANDIDATES = [
  ENV_WS,
  'ws://127.0.0.1:8000/ws/v1/stream',
  'ws://localhost:8000/ws/v1/stream'
].filter(Boolean)

let currentCandidateIndex = 0

const WebSocketContext = createContext<null>(null)

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const store = useAppStore()
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  const connect = useCallback(() => {
    try {
      // rotate through candidates on repeated failures
      const WS_URL = WS_CANDIDATES[currentCandidateIndex % WS_CANDIDATES.length]
      console.log('useWebSocket: attempting connection to', WS_URL, `(candidate ${currentCandidateIndex + 1}/${WS_CANDIDATES.length})`)
      // expose for debugging in browser console
      try {
        ;(window as any).__WS_CANDIDATES = WS_CANDIDATES
        ;(window as any).__WS_TRY_INDEX = currentCandidateIndex
      } catch (e) {}

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
        console.error('WebSocket error event:', error)
        // Some browsers provide little detail in the error event; log the readyState
        console.log('WebSocket readyState:', ws.current?.readyState)
        store.setConnected(false)
      }

      ws.current.onclose = (ev: CloseEvent) => {
        console.log('WebSocket disconnected', { code: ev?.code, reason: ev?.reason, wasClean: ev?.wasClean })
        store.setConnected(false)

        // If connection failed quickly, try next candidate before backoff
        reconnectAttempts.current++
        currentCandidateIndex++

        if (reconnectAttempts.current <= maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000)
          console.log(`Attempting to reconnect (candidate ${currentCandidateIndex % WS_CANDIDATES.length}) in ${delay}ms...`)
          setTimeout(() => connect(), delay)
        } else {
          console.warn('Max reconnect attempts reached for WebSocket')
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

export function WebSocketProvider({ children }: { children: ReactNode }): ReactNode {
  useWebSocket()
  return children
}
