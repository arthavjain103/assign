import { useState, useMemo } from 'react'
import type { VisitorSession } from '../lib/types'
import { ZONE_COLORS } from '../lib/types'

type SortKey = 'entry_time' | 'visitor_id' | 'visit_type' | 'status'

function formatTime(isoString: string | null): string {
  if (!isoString) return '—'
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDwell(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

function ZonePath({ zones }: { zones: string[] }) {
  if (!zones.length) return <span style={{ color: 'var(--text-ghost)', fontSize: 10 }}>—</span>
  return (
    <div className="zone-path">
      {zones.map((z, i) => (
        <span
          key={`${z}-${i}`}
          className="zone-pill"
          style={{
            background: (ZONE_COLORS[z] ?? '#94a3b8') + '20',
            color: ZONE_COLORS[z] ?? '#94a3b8',
          }}
        >
          {i > 0 && <span style={{ color: 'var(--text-ghost)', marginRight: 2, fontSize: 8 }}>›</span>}
          {z}
        </span>
      ))}
    </div>
  )
}

interface SessionTableProps {
  sessions: VisitorSession[]
}

export function SessionTable({ sessions }: SessionTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('entry_time')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sorted = useMemo(() => {
    return [...sessions].sort((a, b) => {
      const va: string = (a[sortKey] as string | null) ?? ''
      const vb: string = (b[sortKey] as string | null) ?? ''
      const cmp = va < vb ? -1 : va > vb ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [sessions, sortKey, sortDir])

  const arrow = (key: SortKey) => {
    if (key !== sortKey) return ' ↕'
    return sortDir === 'asc' ? ' ↑' : ' ↓'
  }

  const nonStaff = sorted.filter(s => !s.is_staff)

  if (!nonStaff.length) {
    return (
      <div style={{ padding: '24px', textAlign: 'center', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-ghost)' }}>
        No sessions recorded yet
      </div>
    )
  }

  return (
    <div className="session-table-wrap">
      <table className="session-table">
        <thead>
          <tr>
            <th onClick={() => handleSort('visitor_id')}>
              VISITOR{arrow('visitor_id')}
            </th>
            <th onClick={() => handleSort('visit_type')}>
              TYPE{arrow('visit_type')}
            </th>
            <th onClick={() => handleSort('entry_time')}>
              ENTRY{arrow('entry_time')}
            </th>
            <th>ZONE PATH</th>
            <th>BILLING</th>
            <th>DWELL</th>
            <th>PURCHASE</th>
            <th onClick={() => handleSort('status')}>
              STATUS{arrow('status')}
            </th>
          </tr>
        </thead>
        <tbody>
          {nonStaff.map(s => (
            <tr key={s.session_id}>
              <td className="visitor-id-cell">
                {s.visitor_id}
                {s.is_returning && (
                  <span style={{ marginLeft: 4, color: 'var(--returning)', fontSize: 9 }}>↩</span>
                )}
              </td>
              <td>
                <span className={`badge badge-${s.visit_type}`}>
                  {s.visit_type === 'group' ? `group·${s.group_size}` : 'solo'}
                </span>
              </td>
              <td>{formatTime(s.entry_time)}</td>
              <td><ZonePath zones={s.zones_visited} /></td>
              <td>{formatTime(s.billing_time)}</td>
              <td>{formatDwell(s.entry_to_purchase_seconds)}</td>
              <td>
                {s.purchase_flag
                  ? <span style={{ color: 'var(--live)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>✓</span>
                  : <span style={{ color: 'var(--text-ghost)' }}>—</span>
                }
              </td>
              <td>
                <span className={`badge badge-${s.status}`}>
                  {s.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
