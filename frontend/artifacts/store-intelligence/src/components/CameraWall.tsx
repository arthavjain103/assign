import React, { useState, useCallback, useRef, useEffect } from 'react'
import type { LiveStats } from '../lib/types'
import { CAMERA_META } from '../lib/types'
import { useWebSocketCamera } from '../hooks/useWebSocketCamera'

const GLOW_WINDOW_MS = 500

const GLOW_COLORS: Record<string, string> = {
  ENTRY:               '#00B876',
  EXIT:                '#E8341A',
  RETURNING_CUSTOMER:  '#D4A017',
  REENTRY:             '#E88C1A',
  ZONE_ENTER:          '#6C3CE1',
  ZONE_DWELL:          '#6C3CE1',
  BILLING_QUEUE_JOIN:  '#E88C1A',
  STAFF_FLAG:          '#0EA5E9',
}

const TYPE_COLORS: Record<string, string> = {
  ENTRY:   '#00B876',
  FLOOR:   '#6C3CE1',
  BILLING: '#E88C1A',
  STAFF:   '#0EA5E9',
}

interface CameraFeedProps {
  cameraId: string
  isHero: boolean
  isGlowing: boolean
  glowColor: string
  visitorCount: number
  gridClass: string
}

const CameraFeed = React.memo(function CameraFeed({
  cameraId, isHero, isGlowing, glowColor, visitorCount, gridClass,
}: CameraFeedProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [offline, setOffline] = useState(false)
  const [isConnected, setIsConnected] = useState(false)
  const meta = CAMERA_META[cameraId]
  const imageRef = useRef<HTMLImageElement | null>(null)

  const handleFrame = useCallback((frameData: string) => {
    if (!canvasRef.current || !imageRef.current) return

    try {
      imageRef.current.src = `data:image/jpeg;base64,${frameData}`
      imageRef.current.onload = () => {
        const ctx = canvasRef.current?.getContext('2d')
        if (ctx && imageRef.current) {
          ctx.drawImage(imageRef.current, 0, 0, canvasRef.current!.width, canvasRef.current!.height)
        }
      }
      setOffline(false)
    } catch (err) {
      console.error('Failed to render frame:', err)
    }
  }, [])

  const handleError = useCallback((error: string) => {
    console.error(`Camera ${cameraId} error:`, error)
    setOffline(true)
  }, [cameraId])

  const { isConnected: wsConnected } = useWebSocketCamera({
    cameraId,
    onFrame: handleFrame,
    onError: handleError,
  })

  useEffect(() => {
    setIsConnected(wsConnected)
  }, [wsConnected])

  // Create hidden image element for image loading
  useEffect(() => {
    if (!imageRef.current) {
      imageRef.current = new Image()
      imageRef.current.crossOrigin = 'anonymous'
    }
  }, [])

  return (
    <div
      className={`camera-feed ${gridClass}${isGlowing ? ' detecting' : ''}`}
      style={isGlowing ? ({ '--glow': glowColor } as React.CSSProperties) : undefined}
    >
      {!offline && isConnected ? (
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
        
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
      ) : (
        <div className="cam-offline">
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
            {cameraId.replace('_', ' ')}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--exit-red)', letterSpacing: '0.06em' }}>
            {offline ? 'FEED OFFLINE' : isConnected ? 'CONNECTING...' : 'DISCONNECTED'}
          </span>
        </div>
      )}

      <div className="cam-badge cam-badge--tl">
        {cameraId.replace('_', ' ')} · {meta?.type}
      </div>

      <div className="cam-badge cam-badge--bl">
        {meta?.zones.join(' · ')}
      </div>

      <div
        className="cam-badge cam-badge--br"
        style={{ color: TYPE_COLORS[meta?.type ?? ''] ?? 'var(--text-secondary)' }}
      >
        ● {visitorCount} seen
      </div>

      {isHero && (
        <div style={{
          position: 'absolute', top: 8, right: 8,
          background: 'rgba(0,87,255,0.12)',
          border: '1px solid rgba(0,87,255,0.25)',
          borderRadius: 4,
          fontFamily: 'var(--font-mono)',
          fontSize: 9,
          fontWeight: 600,
          color: 'var(--accent)',
          padding: '2px 6px',
          letterSpacing: '0.08em',
        }}>
          HERO · ENTRY
        </div>
      )}
    </div>
  )
})

interface CameraWallProps {
  stats: LiveStats
  latestEventPerCamera: Record<string, { type: string; ts: number }>
}

const GRID_CLASSES: Record<string, string> = {
  CAM_3: 'cam-hero',
  CAM_1: 'cam-mid-1',
  CAM_5: 'cam-small-1',
  CAM_2: 'cam-mid-2',
  CAM_4: 'cam-small-2',
}

export function CameraWall({ stats, latestEventPerCamera }: CameraWallProps) {
  const cameraIds = ['CAM_3', 'CAM_1', 'CAM_5', 'CAM_2', 'CAM_4']

  const isGlowing = (id: string) => {
    const ev = latestEventPerCamera[id]
    return !!ev && Date.now() - ev.ts < GLOW_WINDOW_MS
  }

  const glowColor = (id: string) => {
    const ev = latestEventPerCamera[id]
    if (!ev) return '#0057FF'
    return GLOW_COLORS[ev.type] ?? '#0057FF'
  }

  return (
    <div className="camera-mosaic">
      {cameraIds.map(id => (
        <CameraFeed
          key={id}
          cameraId={id}
          isHero={id === 'CAM_3'}
          isGlowing={isGlowing(id)}
          glowColor={glowColor(id)}
          visitorCount={(stats.cameras?.[id]?.visitors ?? 0) as number}
          gridClass={GRID_CLASSES[id] ?? ''}
        />
      ))}
    </div>
  )
}
