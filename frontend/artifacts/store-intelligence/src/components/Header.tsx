import { useEffect, useRef, useState, useCallback } from 'react'
import type { HealthData } from '../lib/types'

interface HeaderProps {
  connected: boolean
  health: HealthData
  eventRate: number
}

const POINT_COUNT = 200

function useAnimatedClock() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
  useEffect(() => {
    const id = setInterval(() => {
      setTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    }, 1000)
    return () => clearInterval(id)
  }, [])
  return time
}

function LivePulse({ eventRate }: { eventRate: number }) {
  const svgRef = useRef<SVGPolylineElement>(null)
  const fillRef = useRef<SVGPolygonElement>(null)
  const points = useRef<number[]>(Array(POINT_COUNT).fill(18))
  const offset = useRef(0)
  const timeRef = useRef(0)
  const rafRef = useRef<number>(0)
  const rateRef = useRef(eventRate)
  const spikeRef = useRef(false)

  useEffect(() => { rateRef.current = eventRate }, [eventRate])

  useEffect(() => {
    const prev = rateRef.current
    if (eventRate > prev) spikeRef.current = true
  }, [eventRate])

  const render = useCallback((ts: number) => {
    const dt = ts - timeRef.current
    timeRef.current = ts
    const step = dt * 0.06

    const amplitude = Math.min(14, Math.max(2, rateRef.current * 4))

    if (spikeRef.current) {
      points.current.push(18 - amplitude * 2.5)
      spikeRef.current = false
    } else {
      const y = 18 + Math.sin(ts * 0.0025) * amplitude + (Math.random() * amplitude * 0.3)
      points.current.push(y)
    }
    if (points.current.length > POINT_COUNT) points.current.shift()

    offset.current = (offset.current + step) % (POINT_COUNT * 3)

    const pts = points.current.map((y, i) => `${i * 3},${y}`).join(' ')
    if (svgRef.current) svgRef.current.setAttribute('points', pts)

    const fillPts = `0,36 ${pts} ${(points.current.length - 1) * 3},36`
    if (fillRef.current) fillRef.current.setAttribute('points', fillPts)

    rafRef.current = requestAnimationFrame(render)
  }, [])

  useEffect(() => {
    rafRef.current = requestAnimationFrame(render)
    return () => cancelAnimationFrame(rafRef.current)
  }, [render])

  return (
    <div className="header-pulse-wrap">
      <svg
        viewBox={`0 0 ${POINT_COUNT * 3} 36`}
        width="100%"
        height="36"
        preserveAspectRatio="none"
        style={{ display: 'block' }}
      >
        <polygon
          ref={fillRef}
          fill="rgba(0,87,255,0.06)"
          stroke="none"
        />
        <polyline
          ref={svgRef}
          fill="none"
          stroke="#0057FF"
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>
    </div>
  )
}

export function Header({ connected, health, eventRate }: HeaderProps) {
  const time = useAnimatedClock()

  const healthColor =
    health.status === 'healthy' ? 'var(--live)' :
    health.status === 'degraded' ? 'var(--warn)' :
    'var(--text-ghost)'

  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo">SI</div>
        <div className="header-brand-text">
          <span className="header-brand-title">Store Intelligence</span>
          <span className="header-brand-sub">ST1008 · BRIGADE RD</span>
        </div>
      </div>

      <LivePulse eventRate={eventRate} />

      <div className="header-status">
        <div className="status-pill" style={{ color: connected ? 'var(--live)' : 'var(--warn)' }}>
          <span
            className={`status-dot ${connected ? 'status-dot--live' : 'status-dot--warn'}`}
            aria-hidden="true"
          />
          {connected ? 'LIVE' : 'CONNECTING'}
        </div>
        <div
          className="status-pill"
          style={{ color: healthColor }}
          title={`System: ${health.status}`}
        >
          <span className="status-dot" style={{ background: healthColor }} aria-hidden="true" />
          {health.status.toUpperCase()}
        </div>
        <span className="clock" aria-live="polite" aria-label="Current time">{time}</span>
      </div>
    </header>
  )
}
