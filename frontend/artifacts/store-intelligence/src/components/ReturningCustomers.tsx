import { useRef, useEffect, useState } from 'react'
import type { ReturningProfile, StoreEvent } from '../lib/types'

const AVATAR_COLORS = ['#0057FF','#6C3CE1','#00B876','#E88C1A','#E8341A','#0EA5E9']

function avatarColor(visitorId: string): string {
  const hash = visitorId.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0)
  return AVATAR_COLORS[hash % AVATAR_COLORS.length]
}

function avatarInitials(visitorId: string): string {
  return visitorId.replace('VIS_', 'V')
}

function relativeTime(isoString: string | null): string {
  if (!isoString) return '—'
  const diff = (Date.now() - new Date(isoString).getTime()) / 1000
  if (diff < 60)   return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(isoString).toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function methodLabel(method: string): string {
  const map: Record<string, string> = {
    face_sface: 'Face · SFace',
    face_haar:  'Face · Haar',
    body:       'Body signature',
    reentry:    'Re-entry',
    new:        'New visitor',
  }
  return map[method] ?? method
}

function VisitDots({ count }: { count: number }) {
  const MAX = 5
  const filled = Math.min(count, MAX)
  const extra = count > MAX ? count - MAX : 0
  return (
    <div className="returning-dots" aria-label={`${count} visits`}>
      {Array.from({ length: filled }, (_, i) => (
        <span key={`f-${i}`} className="ret-dot ret-dot--filled" aria-hidden="true" />
      ))}
      {Array.from({ length: Math.max(0, MAX - filled) }, (_, i) => (
        <span key={`e-${i}`} className="ret-dot ret-dot--empty" aria-hidden="true" />
      ))}
      {extra > 0 && (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)' }}>
          +{extra}
        </span>
      )}
    </div>
  )
}

interface ReturningCustomersProps {
  profiles: ReturningProfile[]
  latestEvent: StoreEvent | undefined
}

export function ReturningCustomers({ profiles, latestEvent }: ReturningCustomersProps) {
  const prevIdsRef = useRef(new Set<string>())
  const [newIds, setNewIds] = useState(new Set<string>())

  useEffect(() => {
    const incoming = new Set<string>()
    profiles.forEach(p => {
      if (!prevIdsRef.current.has(p.visitor_id)) incoming.add(p.visitor_id)
    })
    setNewIds(incoming)
    prevIdsRef.current = new Set(profiles.map(p => p.visitor_id))
  }, [profiles])

  // Watch for new RETURNING_CUSTOMER events
  useEffect(() => {
    if (latestEvent?.event_type === 'RETURNING_CUSTOMER' && latestEvent.visitor_id) {
      setNewIds(prev => new Set([...prev, latestEvent.visitor_id!]))
      const timer = setTimeout(() => {
        setNewIds(prev => {
          const next = new Set(prev)
          next.delete(latestEvent.visitor_id!)
          return next
        })
      }, 1500)
      return () => clearTimeout(timer)
    }
    return undefined
  }, [latestEvent])

  if (!profiles.length) {
    return (
      <div style={{
        padding: '20px 12px',
        textAlign: 'center',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--text-ghost)',
      }}>
        No returning customers yet
      </div>
    )
  }

  return (
    <div className="returning-list">
      {profiles.map(profile => (
        <div
          key={profile.visitor_id}
          className={`returning-card${newIds.has(profile.visitor_id) ? ' new-entry' : ''}`}
        >
          <div
            className="returning-avatar"
            style={{ background: avatarColor(profile.visitor_id) }}
            aria-hidden="true"
          >
            {avatarInitials(profile.visitor_id)}
          </div>
          <div className="returning-info">
            <div className="returning-id-row">
              <span className="returning-id">{profile.visitor_id}</span>
              <span className="returning-visits">↩ {profile.visit_count}</span>
            </div>
            <div className="returning-method">
              {methodLabel(profile.recognition_method)} ·{' '}
              {Math.round(profile.last_confidence * 100)}% match
            </div>
            <VisitDots count={profile.visit_count} />
            <div className="returning-last">
              Last: {relativeTime(profile.last_seen)}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
