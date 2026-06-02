import type { FunnelData } from '../lib/types'

interface FunnelStage {
  label: string
  value: number
  color: string
}

function polarToCart(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}
// Suppress unused warning
void polarToCart

const MAX_W = 280
const MIN_W = 48
const TOTAL_H = 220
const GAP = 3

function FunnelChart({ stages }: { stages: FunnelStage[] }) {
  const maxVal = Math.max(...stages.map(s => s.value), 1)
  const stageH = (TOTAL_H - GAP * (stages.length - 1)) / stages.length

  return (
    <svg
      viewBox={`0 0 ${MAX_W} ${TOTAL_H}`}
      width="100%"
      height={TOTAL_H}
      style={{ display: 'block' }}
      aria-label="Customer flow funnel"
      role="img"
    >
      {stages.map((stage, i) => {
        const thisW = MIN_W + (stage.value / maxVal) * (MAX_W - MIN_W)
        const nextStage = stages[i + 1]
        const nextW = nextStage
          ? MIN_W + (nextStage.value / maxVal) * (MAX_W - MIN_W)
          : thisW * 0.72

        const y = i * (stageH + GAP)
        const lt = (MAX_W - thisW) / 2
        const rt = lt + thisW
        const lb = (MAX_W - nextW) / 2
        const rb = lb + nextW

        const dropOff = nextStage && stage.value > 0
          ? Math.round(((stage.value - nextStage.value) / stage.value) * 100)
          : null

        const midY = y + stageH / 2

        return (
          <g key={stage.label}>
            <polygon
              points={`${lt},${y + 2} ${rt},${y + 2} ${rb},${y + stageH - 2} ${lb},${y + stageH - 2}`}
              fill={stage.color}
              opacity="0.88"
            />
            <text
              x={MAX_W / 2}
              y={midY - 7}
              textAnchor="middle"
              fontFamily="var(--font-mono)"
              fontSize="9"
              fontWeight="500"
              fill="rgba(255,255,255,0.85)"
              letterSpacing="0.08"
            >
              {stage.label}
            </text>
            <text
              x={MAX_W / 2}
              y={midY + 9}
              textAnchor="middle"
              fontFamily="var(--font-mono)"
              fontSize="18"
              fontWeight="700"
              fill="white"
            >
              {stage.value}
            </text>
            {dropOff !== null && (
              <text
                x={rt + 6}
                y={y + stageH + 1}
                fontFamily="var(--font-mono)"
                fontSize="9"
                fill="var(--text-muted)"
              >
                ▼{dropOff}%
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}

interface CustomerFlowFunnelProps {
  funnel: FunnelData
}

export function CustomerFlowFunnel({ funnel }: CustomerFlowFunnelProps) {
  const stages: FunnelStage[] = [
    { label: 'ENTRY',    value: funnel.entry,      color: '#0057FF' },
    { label: 'BROWSING', value: funnel.zone_visit,  color: '#6C3CE1' },
    { label: 'BILLING',  value: funnel.billing,     color: '#E88C1A' },
    { label: 'PURCHASE', value: funnel.purchase,    color: '#00B876' },
  ]

  const conversionRate = funnel.entry > 0
    ? Math.round((funnel.purchase / funnel.entry) * 100)
    : 0

  return (
    <div className="funnel-wrap">
      <FunnelChart stages={stages} />
      <div className="funnel-legend">
        {stages.map((s, i) => {
          const next = stages[i + 1]
          const drop = next && s.value > 0
            ? Math.round(((s.value - next.value) / s.value) * 100)
            : null
          return (
            <div key={s.label} className="funnel-legend-row">
              <span className="funnel-legend-label" style={{ color: s.color }}>
                {s.label}
              </span>
              <span className="funnel-legend-val">{s.value}</span>
              {drop !== null && (
                <span className="funnel-legend-drop">-{drop}%</span>
              )}
            </div>
          )
        })}
        <div
          className="funnel-legend-row"
          style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border-faint)' }}
        >
          <span className="funnel-legend-label">CONVERSION</span>
          <span
            className="funnel-legend-val"
            style={{ color: conversionRate >= 15 ? 'var(--live)' : conversionRate >= 8 ? 'var(--warn)' : 'var(--exit-red)' }}
          >
            {conversionRate}%
          </span>
        </div>
      </div>
    </div>
  )
}
