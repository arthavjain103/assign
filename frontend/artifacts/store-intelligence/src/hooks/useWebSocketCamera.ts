import { useEffect, useRef, useState } from 'react'

interface UseWebSocketCameraOptions {
  cameraId: string
  onFrame?: (frameData: string) => void
  onError?: (error: string) => void
}

export function useWebSocketCamera({ cameraId, onFrame, onError }: UseWebSocketCameraOptions) {
  const ws = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5

  useEffect(() => {
    if (!cameraId) return

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const apiHost = window.location.hostname === 'localhost' 
        ? 'localhost:8000' 
        : window.location.host
      const wsUrl = `${protocol}//${apiHost}/ws/camera/${cameraId}`
      console.log(`[WebSocket] Connecting to ${wsUrl}`)

      try {
        ws.current = new WebSocket(wsUrl)

        ws.current.onopen = () => {
          setIsConnected(true)
          reconnectAttempts.current = 0
        }

        ws.current.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            if (message.type === 'frame' && message.data && onFrame) {
              onFrame(message.data)
            } else if (message.error && onError) {
              onError(message.error)
            }
          } catch (err) {
            console.error('Failed to parse WebSocket message:', err)
          }
        }

        ws.current.onerror = (error) => {
          console.error('WebSocket error:', error)
          setIsConnected(false)
          if (onError) {
            onError('WebSocket connection error')
          }
        }

        ws.current.onclose = () => {
          setIsConnected(false)
          
          // Attempt to reconnect with exponential backoff
          if (reconnectAttempts.current < maxReconnectAttempts) {
            reconnectAttempts.current += 1
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current - 1), 10000)
            setTimeout(connectWebSocket, delay)
          }
        }
      } catch (err) {
        console.error('Failed to create WebSocket:', err)
        if (onError) {
          onError('Failed to create WebSocket connection')
        }
      }
    }

    connectWebSocket()

    return () => {
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [cameraId, onFrame, onError])

  return { isConnected }
}
