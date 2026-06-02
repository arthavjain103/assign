import { useEffect, useRef, useState } from 'react'
import type { LiveStats } from '../lib/types'

interface KPICommandBarProps {
  stats: LiveStats
  kpiHistory: Record<string, number[]>
}

function useAnimatedNumber(target: number, duration = 350) {
  const [display, setDisplay] = useState(target)
  const prevRef = useRef(target)
  useEffect(() => {
    const start = prevRef.current
    const delta = target - start
    if (delta === 0) return
    prevRef.current = target
    let startTime: number | null = null
    const raf = (time: number) => {
      if (!startTime) startTime = time
      const elapsed = time - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.round(start + delta * eased))
      if (progress < 1) requestAnimationFrame(raf)
    }
    requestAnimationFrame(raf)
  }, [target, duration])
  return display
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (!values.length) return <div style={{ width: 52, height: 18 }} />
  const max = Math.max(...values, 1)
  const w = 52
  const h = 18
  const step = w / Math.max(values.length - 1, 1)
  const pts = values.map((v, i) => `${i * step},${h - (v / max) * (h - 2) - 1}`).join(' ')

  return (
    <svg width={w} height={h} style={{ overflow: 'visible', flexShrink: 0 }} aria-hidden="true">
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity="0.55"
      />
    </svg>
  )
}

const CARDS: Array<{
  key: keyof LiveStats
  label: string
  color: string
  sub?: string
}> = [
  { key: 'visitors',    label: 'VISITORS',  color: 'var(--accent)' },
  { key: 'solo',        label: 'SOLO',      color: 'var(--zone)' },
  { key: 'groups',      label: 'GROUPS',    color: 'var(--zone)', sub: 'groups' },
  { key: 'returning',   label: '↩ RETURN',  color: 'var(--returning)' },
  { key: 'new_visitors',label: 'NEW',       color: 'var(--accent)' },
  { key: 'staff',       label: 'STAFF',     color: 'var(--staff)' },
  { key: 'entries',     label: 'ENTRIES',   color: 'var(--live)' },
  { key: 'exits',       label: 'EXITS',     color: 'var(--exit-red)' },
  { key: 'queue_depth', label: 'QUEUE',     color: 'var(--warn)' },
]

interface KPICardProps {
  label: string
  value: number
  history: number[]
  color: string
  alert?: boolean
}

function KPICard({ label, value, history, color, alert }: KPICardProps) {
  const displayed = useAnimatedNumber(value)

  return (
    <div
      className={`kpi-card${alert ? ' kpi-card--alert' : ''}`}
      style={{ color }}
      role="group"
      aria-label={`${label}: ${value}`}
    >
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        <Sparkline values={history} color={color} />
      </div>
      <div className="kpi-bottom">
        <span className="kpi-number" style={{ color }}>
          {displayed}
        </span>
      </div>
    </div>
  )
}

export function KPICommandBar({ stats, kpiHistory }: KPICommandBarProps) {
  return (
    <div className="kpi-bar" role="region" aria-label="Key performance indicators">
      {CARDS.map(({ key, label, color }) => {
        const value = (stats[key] ?? 0) as number
        const isQueue = key === 'queue_depth'
        const alertColor = isQueue && value >= 7 ? 'var(--exit-red)' : color

        return (
          <KPICard
            key={key}
            label={label}
            value={value}
            history={kpiHistory[key] ?? []}
            color={alertColor}
            alert={isQueue && value >= 7}
          />
        )
      })}
    </div>
  )
}
