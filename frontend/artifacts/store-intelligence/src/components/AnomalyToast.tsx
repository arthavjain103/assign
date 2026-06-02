import { useState, useEffect, useCallback, useRef } from 'react'
import type { AnomalyItem } from '../lib/types'

const COOLDOWN_MS = 60_000
const AUTO_DISMISS_MS = 8_000

interface ToastItem {
  id: string
  anomaly: AnomalyItem
  exiting: boolean
}

interface AnomalyToastProps {
  anomalies: AnomalyItem[]
}

const SEVERITY_ICONS: Record<string, string> = {
  WARN: '⚠',
  INFO: 'ℹ',
}

export function AnomalyToast({ anomalies }: AnomalyToastProps) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const seenRef = useRef<Map<string, number>>(new Map())

  const dismiss = useCallback((id: string) => {
    setToasts(prev =>
      prev.map(t => t.id === id ? { ...t, exiting: true } : t)
    )
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 210)
  }, [])

  useEffect(() => {
    anomalies.forEach(anomaly => {
      const key = anomaly.type
      const lastSeen = seenRef.current.get(key) ?? 0
      const now = Date.now()
      if (now - lastSeen < COOLDOWN_MS) return

      seenRef.current.set(key, now)
      const id = `${key}-${now}`

      setToasts(prev => [...prev, { id, anomaly, exiting: false }])

      setTimeout(() => dismiss(id), AUTO_DISMISS_MS)
    })
  }, [anomalies, dismiss])

  if (!toasts.length) return null

  return (
    <div className="toast-container" role="alert" aria-live="assertive">
      {toasts.map(({ id, anomaly, exiting }) => (
        <div
          key={id}
          className={`toast toast--${anomaly.severity}${exiting ? ' exiting' : ''}`}
        >
          <div className="toast-header">
            <span style={{ fontSize: 14, flexShrink: 0 }} aria-hidden="true">
              {SEVERITY_ICONS[anomaly.severity] ?? '●'}
            </span>
            <span className="toast-type">{anomaly.type.replace(/_/g, ' ')}</span>
            <button
              className="toast-close"
              onClick={() => dismiss(id)}
              aria-label="Dismiss alert"
            >
              ×
            </button>
          </div>
          <p className="toast-msg">{anomaly.message}</p>
          <p className="toast-action">↳ {anomaly.suggested_action}</p>
          <div className="toast-progress" aria-hidden="true" />
        </div>
      ))}
    </div>
  )
}
