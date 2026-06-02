import type { AnomalyItem } from '../lib/types'

const SEVERITY_ICONS: Record<string, string> = {
  WARN: '⚠',
  INFO: 'ℹ',
}

interface AnomalyPanelProps {
  anomalies: AnomalyItem[]
}

export function AnomalyPanel({ anomalies }: AnomalyPanelProps) {
  if (!anomalies.length) {
    return (
      <div className="anomaly-nominal">
        <span style={{ fontSize: 14 }} aria-hidden="true">✓</span>
        <span className="anomaly-nominal-text">All systems nominal</span>
      </div>
    )
  }

  return (
    <div className="anomaly-list" role="list" aria-label="System alerts">
      {anomalies
        .filter(a => a && a.type && a.severity)
        .map((a, i) => (
        <div
          key={`${a.type}-${i}`}
          className={`anomaly-strip anomaly-strip--${a.severity}`}
          role="listitem"
        >
          <span className="anomaly-strip-icon" aria-hidden="true">
            {SEVERITY_ICONS[a.severity] ?? '●'}
          </span>
          <div className="anomaly-strip-body">
            <div className="anomaly-strip-type">{a.type.replace(/_/g, ' ')}</div>
            <div className="anomaly-strip-msg">{a.message}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
