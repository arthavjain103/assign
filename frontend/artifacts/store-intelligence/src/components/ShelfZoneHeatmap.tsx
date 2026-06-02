import { useState, useEffect } from 'react'
import type { StoreEvent } from '../lib/types'
import { ZONE_COLORS } from '../lib/types'

const ZONE_BRANDS: Record<string, string[]> = {
  ENTRANCE:    [],
  SKINCARE:    ['TFS', 'GV', 'Minimalist', 'Dot & Key'],
  MAKEUP:      ['NY', 'Colorbar', 'Swiss Beauty', 'Faces'],
  HAIRCARE:    ['Mamaearth', 'Wow', 'Streax', 'TRESemmé'],
  BILLING:     [],
  BACK_OFFICE: [],
}

const ZONE_LABELS: Record<string, string> = {
  ENTRANCE:    'Entrance',
  SKINCARE:    'Skincare',
  MAKEUP:      'Makeup',
  HAIRCARE:    'Haircare',
  BILLING:     'Billing',
  BACK_OFFICE: 'Back Office',
}

const DISPLAY_ZONES = ['SKINCARE', 'MAKEUP', 'HAIRCARE', 'BILLING', 'ENTRANCE']
const INACTIVE_THRESHOLD_MS = 5 * 60 * 1000

interface ShelfZoneHeatmapProps {
  visits: Record<string, number>
  events: StoreEvent[]
}

export function ShelfZoneHeatmap({ visits, events }: ShelfZoneHeatmapProps) {
  const [zoneFlash, setZoneFlash] = useState<Record<string, number>>({})
  const [zoneLastActive, setZoneLastActive] = useState<Record<string, number>>({})

  useEffect(() => {
    const latest = events[0]
    if (!latest) return
    const zoneId = latest.zone_id
    if (!zoneId) return
    if (latest.event_type === 'ZONE_ENTER' || latest.event_type === 'ZONE_DWELL') {
      const now = Date.now()
      setZoneFlash(prev => ({ ...prev, [zoneId]: now }))
      setZoneLastActive(prev => ({ ...prev, [zoneId]: now }))
    }
  }, [events])

  const maxVisits = Math.max(...DISPLAY_ZONES.map(z => visits[z] ?? 0), 1)

  return (
    <div className="zone-grid">
      {DISPLAY_ZONES.map(zoneId => {
        const color = ZONE_COLORS[zoneId] ?? '#94a3b8'
        const count = visits[zoneId] ?? 0
        const intensity = count / maxVisits
        const flashTs = zoneFlash[zoneId] ?? 0
        const isFlashing = Date.now() - flashTs < 600
        const lastActive = zoneLastActive[zoneId] ?? 0
        const isInactive = lastActive > 0 && Date.now() - lastActive > INACTIVE_THRESHOLD_MS
        const brands = ZONE_BRANDS[zoneId] ?? []

        return (
          <div
            key={zoneId}
            className={`zone-card${isFlashing ? ' flashing' : ''}`}
            style={{ '--zone-flash-color': color } as React.CSSProperties}
          >
            <div className="zone-card-name">
              <span className="zone-dot" style={{ background: color }} aria-hidden="true" />
              {ZONE_LABELS[zoneId] ?? zoneId}
            </div>
            <div className="zone-count" style={{ color }}>
              {count}
            </div>
            <div className="zone-bar-track">
              <div
                className="zone-bar-fill"
                style={{ width: `${intensity * 100}%`, background: color }}
                role="progressbar"
                aria-valuenow={Math.round(intensity * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${ZONE_LABELS[zoneId]} activity`}
              />
            </div>
            {brands.length > 0 && (
              <div className="zone-brands">{brands.slice(0, 3).join(' · ')}</div>
            )}
            {isInactive && (
              <div className="zone-inactive">INACTIVE</div>
            )}
          </div>
        )
      })}
    </div>
  )
}
