import type { QueueSnapshot } from '../lib/types'

const CX = 120
const CY = 115
const R  = 80
const START_DEG = -210
const END_DEG   = 30
const SWEEP     = 240

function toRad(deg: number) { return (deg * Math.PI) / 180 }

function polarToCart(cx: number, cy: number, r: number, deg: number) {
  return {
    x: cx + r * Math.cos(toRad(deg)),
    y: cy + r * Math.sin(toRad(deg)),
  }
}

function describeArc(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string {
  const start = polarToCart(cx, cy, r, startDeg)
  const end   = polarToCart(cx, cy, r, endDeg)
  const largeArc = endDeg - startDeg > 180 ? 1 : 0
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`
}

interface QueueGaugeProps {
  depth: number
  history: QueueSnapshot[]
}

export function QueueGauge({ depth, history }: QueueGaugeProps) {
  const MAX = 10
  const clamped = Math.min(depth, MAX)
  const valueDeg = START_DEG + (clamped / MAX) * SWEEP
  const needleEnd = polarToCart(CX, CY, 62, valueDeg)

  const arcColor =
    depth >= 7 ? '#E8341A' :
    depth >= 4 ? '#E88C1A' :
    '#00B876'

  const isAlert = depth >= 7
  const waitSec = depth * 90
  const waitLabel = waitSec >= 60
    ? `~${Math.round(waitSec / 60)}m wait`
    : `~${waitSec}s wait`

  const sparkMax = Math.max(...history.map(h => h.queue_depth), 1)

  return (
    <div className={`gauge-wrap${isAlert ? ' gauge-alert' : ''}`}>
      <svg
        viewBox="0 0 240 140"
        width="100%"
        height="140"
        role="img"
        aria-label={`Billing queue depth: ${depth}`}
      >
        <path
          d={describeArc(CX, CY, R, START_DEG, END_DEG)}
          fill="none"
          stroke="var(--border-normal)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {depth > 0 && (
          <path
            d={describeArc(CX, CY, R, START_DEG, valueDeg)}
            fill="none"
            stroke={arcColor}
            strokeWidth="10"
            strokeLinecap="round"
            style={{ transition: 'all 400ms cubic-bezier(0.16,1,0.3,1)' }}
          />
        )}
        <line
          x1={CX} y1={CY}
          x2={needleEnd.x} y2={needleEnd.y}
          stroke="var(--text-primary)"
          strokeWidth="2"
          strokeLinecap="round"
          style={{ transition: 'all 400ms cubic-bezier(0.16,1,0.3,1)', transformOrigin: `${CX}px ${CY}px` }}
        />
        <circle cx={CX} cy={CY} r="5" fill="var(--text-primary)" />
        <circle cx={CX} cy={CY} r="3" fill="var(--bg-surface)" />

        <text
          x={CX} y={CY - 12}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize="36"
          fontWeight="700"
          fill={arcColor}
        >
          {depth}
        </text>
        <text
          x={CX} y={CY + 12}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize="10"
          fill="var(--text-muted)"
        >
          {waitLabel}
        </text>

        <text
          x={polarToCart(CX, CY, R + 14, START_DEG).x}
          y={polarToCart(CX, CY, R + 14, START_DEG).y + 4}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize="8"
          fill="var(--text-ghost)"
        >
          0
        </text>
        <text
          x={polarToCart(CX, CY, R + 14, END_DEG).x}
          y={polarToCart(CX, CY, R + 14, END_DEG).y + 4}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize="8"
          fill="var(--text-ghost)"
        >
          {MAX}
        </text>
      </svg>

      {history.length > 0 && (
        <div className="gauge-sparkline">
          {history.slice(-20).map((snap, i) => {
            const h = Math.max((snap.queue_depth / sparkMax) * 24, 2)
            const barColor =
              snap.queue_depth >= 7 ? 'var(--exit-red)' :
              snap.queue_depth >= 4 ? 'var(--warn)' :
              'var(--live)'
            return (
              <div
                key={i}
                className="gauge-bar"
                style={{ height: h, background: barColor, opacity: 0.65 }}
                aria-hidden="true"
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
