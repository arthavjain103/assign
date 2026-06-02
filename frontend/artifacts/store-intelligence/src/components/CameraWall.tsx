import React, { useState, useCallback, useRef, useEffect } from 'react'
import type { LiveStats, CameraMeta } from '../lib/types'
import { CAMERA_META } from '../lib/types'
import { wsCameraUrl } from '../lib/api'

// ─── Constants ────────────────────────────────────────────────────────────────

const GLOW_WINDOW_MS = 600

const GLOW_COLORS: Record<string, string> = {
  ENTRY:               '#00D98B',
  EXIT:                '#FF4D4D',
  RETURNING_CUSTOMER:  '#FFA834',
  REENTRY:             '#FFA834',
  ZONE_ENTER:          '#7C3AED',
  ZONE_DWELL:          '#7C3AED',
  BILLING_QUEUE_JOIN:  '#FFA834',
  BILLING_QUEUE_ABANDON: '#FF4D4D',
  STAFF_FLAG:          '#38BDF8',
}

const TYPE_BADGE_COLORS: Record<string, string> = {
  ENTRY:   '#00D98B',
  FLOOR:   '#7C3AED',
  BILLING: '#FFA834',
  STAFF:   '#38BDF8',
}

// ─── Offline Tile ─────────────────────────────────────────────────────────────

function OfflineTile({ meta, cameraId }: { meta: CameraMeta; cameraId: string }) {
  return (
    <div className="cam-offline-tile">
      <div className="cam-offline-icon">
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M15 10l4.553-2.069A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.89L15 14M3 8a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" strokeLinecap="round" strokeLinejoin="round" />
          <line x1="2" y1="2" x2="22" y2="22" strokeLinecap="round" />
        </svg>
      </div>
      <span className="cam-offline-label">{meta.label}</span>
      <span className="cam-offline-badge">NO FEED</span>
      <span className="cam-offline-zones">{meta.zones.join(' · ')}</span>
    </div>
  )
}

// ─── Live Camera Feed ─────────────────────────────────────────────────────────

interface CameraFeedProps {
  cameraId: string
  meta: CameraMeta
  isHero: boolean
  isGlowing: boolean
  glowColor: string
  visitorCount: number
  gridClass: string
}

const CameraFeed = React.memo(function CameraFeed({
  cameraId, meta, isHero, isGlowing, glowColor, visitorCount, gridClass,
}: CameraFeedProps) {
  const canvasRef   = useRef<HTMLCanvasElement>(null)
  const imageRef    = useRef<HTMLImageElement | null>(null)
  const wsRef       = useRef<WebSocket | null>(null)
  const retryRef    = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryCount  = useRef(0)
  const [wsOk, setWsOk]       = useState(false)
  const [offline, setOffline]  = useState(false)

  // Create off-screen image once
  useEffect(() => {
    if (!imageRef.current) {
      imageRef.current = new Image()
      imageRef.current.crossOrigin = 'anonymous'
    }
  }, [])

  const drawFrame = useCallback((b64: string) => {
    if (!canvasRef.current || !imageRef.current) return
    imageRef.current.onload = () => {
      const ctx = canvasRef.current?.getContext('2d')
      if (ctx && imageRef.current) {
        ctx.drawImage(imageRef.current, 0, 0, canvasRef.current!.width, canvasRef.current!.height)
      }
    }
    imageRef.current.src = `data:image/jpeg;base64,${b64}`
    setOffline(false)
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current) wsRef.current.close()
    const ws = new WebSocket(wsCameraUrl(cameraId))
    wsRef.current = ws

    ws.onopen  = () => { setWsOk(true); retryCount.current = 0 }
    ws.onclose = () => {
      setWsOk(false)
      // exponential back-off up to 15 s
      const delay = Math.min(1000 * Math.pow(2, retryCount.current), 15000)
      retryCount.current++
      retryRef.current = setTimeout(connect, delay)
    }
    ws.onerror = () => { setOffline(true) }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string)
        if (msg.type === 'frame' && msg.data) drawFrame(msg.data)
        if (msg.error) setOffline(true)
      } catch { /* ignore */ }
    }
  }, [cameraId, drawFrame])

  useEffect(() => {
    connect()
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return (
    <div
      className={`camera-feed ${gridClass}${isGlowing ? ' detecting' : ''}`}
      style={isGlowing ? ({ '--glow': glowColor } as React.CSSProperties) : undefined}
    >
      {wsOk && !offline ? (
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
      ) : (
        <div className="cam-offline">
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
            {meta.label}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--exit-red)', letterSpacing: '0.06em' }}>
            {offline ? 'FEED OFFLINE' : 'CONNECTING…'}
          </span>
        </div>
      )}

      {/* Top-left badge */}
      <div className="cam-badge cam-badge--tl">
        {meta.label} · <span style={{ color: TYPE_BADGE_COLORS[meta.type] ?? 'var(--text-secondary)' }}>{meta.type}</span>
      </div>

      {/* Bottom-left zones */}
      <div className="cam-badge cam-badge--bl">{meta.zones.join(' · ')}</div>

      {/* Bottom-right visitor count */}
      <div className="cam-badge cam-badge--br" style={{ color: TYPE_BADGE_COLORS[meta.type] ?? 'var(--text-secondary)' }}>
        ● {visitorCount} seen
      </div>

      {/* Hero marker */}
      {isHero && (
        <div className="cam-hero-pill">HERO · ENTRY</div>
      )}

      {/* Live indicator */}
      {wsOk && !offline && (
        <div className="cam-live-dot" />
      )}
    </div>
  )
})

// ─── CameraWall ───────────────────────────────────────────────────────────────

interface CameraWallProps {
  stats: LiveStats
  latestEventPerCamera: Record<string, { type: string; ts: number }>
}

/**
 * Camera order: live cameras first, then offline tiles.
 * Grid classes defined below are CSS-grid area names.
 */
const CAMERA_ORDER = ['CAM_1', 'CAM_2', 'CAM_3', 'CAM_4', 'CAM_5'] as const

const GRID_CLASSES: Record<string, string> = {
  CAM_1: 'cam-hero',
  CAM_2: 'cam-mid-1',
  CAM_3: 'cam-small-1',
  CAM_4: 'cam-mid-2',
  CAM_5: 'cam-small-2',
}

export function CameraWall({ stats, latestEventPerCamera }: CameraWallProps) {
  const isGlowing = (id: string) => {
    const ev = latestEventPerCamera[id]
    return !!ev && Date.now() - ev.ts < GLOW_WINDOW_MS
  }

  const glowColor = (id: string) => {
    const ev = latestEventPerCamera[id]
    if (!ev) return '#1B6FFF'
    return GLOW_COLORS[ev.type] ?? '#1B6FFF'
  }

  return (
    <div className="camera-mosaic">
      {CAMERA_ORDER.map(id => {
        const meta = CAMERA_META[id]
        if (!meta) return null

        if (!meta.live) {
          return (
            <div key={id} className={`camera-feed ${GRID_CLASSES[id] ?? ''} cam-offline-wrapper`}>
              <OfflineTile meta={meta} cameraId={id} />
            </div>
          )
        }

        return (
          <CameraFeed
            key={id}
            cameraId={id}
            meta={meta}
            isHero={id === 'CAM_1'}
            isGlowing={isGlowing(id)}
            glowColor={glowColor(id)}
            visitorCount={(stats.cameras?.[id]?.visitors ?? 0) as number}
            gridClass={GRID_CLASSES[id] ?? ''}
          />
        )
      })}
    </div>
  )
}
