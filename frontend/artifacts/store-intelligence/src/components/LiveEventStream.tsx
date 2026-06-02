import { useState, useEffect, useRef } from 'react'
import type { StoreEvent } from '../lib/types'
import { EVENT_LABELS } from '../lib/types'

function relativeTime(isoString: string): string {
  const diff = (Date.now() - new Date(isoString).getTime()) / 1000
  if (diff < 5)  return 'just now'
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

interface EventRowProps {
  event: StoreEvent
  isNew: boolean
}

function EventRow({ event, isNew }: EventRowProps) {
  return (
    <div
      className={`event-row event-${event.event_type}${isNew ? ' event-entering' : ''}`}
      role="listitem"
    >
      <span className="event-chip">
        {EVENT_LABELS[event.event_type] ?? event.event_type}
      </span>
      <div className="event-body">
        {event.visitor_id && (
          <span className="event-visitor">{event.visitor_id}</span>
        )}
        {event.zone_id && (
          <span className="event-zone">→ {event.zone_id}</span>
        )}
        {event.visit_type && !event.is_staff && (
          <span style={{ color: 'var(--text-ghost)', fontSize: 9 }}>{event.visit_type}</span>
        )}
        {event.is_staff && (
          <span style={{ color: 'var(--staff)', fontSize: 9, fontFamily: 'var(--font-mono)' }}>STAFF</span>
        )}
        {event.queue_depth != null && event.event_type === 'BILLING_QUEUE_JOIN' && (
          <span style={{ color: 'var(--warn)', fontSize: 9, fontFamily: 'var(--font-mono)' }}>
            q={event.queue_depth}
          </span>
        )}
      </div>
      <div className="event-meta">
        <span className="event-cam">{event.camera_id ?? ''}</span>
        <span className="event-time">{relativeTime(event.timestamp)}</span>
      </div>
    </div>
  )
}

interface LiveEventStreamProps {
  events: StoreEvent[]
}

export function LiveEventStream({ events }: LiveEventStreamProps) {
  const [, setTick] = useState(0)
  const prevIdsRef = useRef(new Set<string>())
  const newIdsRef = useRef(new Set<string>())

  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 5000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const incoming = new Set<string>()
    events.forEach(e => {
      if (!prevIdsRef.current.has(e.event_id)) {
        incoming.add(e.event_id)
      }
    })
    newIdsRef.current = incoming
    prevIdsRef.current = new Set(events.map(e => e.event_id))
  }, [events])

  if (!events.length) {
    return (
      <div style={{
        padding: '24px 16px',
        textAlign: 'center',
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        color: 'var(--text-ghost)',
      }}>
        Awaiting events...
      </div>
    )
  }

  return (
    <div className="event-list" role="list" aria-label="Live event stream" aria-live="polite">
      {events.map(event => (
        <EventRow
          key={event.event_id}
          event={event}
          isNew={newIdsRef.current.has(event.event_id)}
        />
      ))}
    </div>
  )
}
