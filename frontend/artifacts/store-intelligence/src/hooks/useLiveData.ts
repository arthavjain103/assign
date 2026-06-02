import { useState, useEffect, useRef, useCallback } from 'react'
import type {
  StoreEvent, VisitorSession, QueueSnapshot,
  LiveStats, AnomalyItem, ReturningProfile,
  FunnelData, HealthData,
} from '../lib/types'
import {
  startStreams, fetchStats, fetchEvents, fetchSessions,
  fetchQueue, fetchAnomalies, fetchReturningCustomers,
  fetchHealth, fetchFunnel, wsEventsUrl,
} from '../lib/api'

const EMPTY_STATS: LiveStats = {
  visitors: 0, staff: 0, solo: 0, groups: 0,
  entries: 0, exits: 0, queue_depth: 0, returning: 0, new_visitors: 0,
}

const KPI_KEYS = ['visitors','staff','solo','groups','entries','exits','queue_depth','returning'] as const

export interface LiveDataReturn {
  events: StoreEvent[]
  sessions: VisitorSession[]
  stats: LiveStats
  queueHistory: QueueSnapshot[]
  shelfVisits: Record<string, number>
  connected: boolean
  anomalies: AnomalyItem[]
  returningProfiles: ReturningProfile[]
  health: HealthData
  eventRate: number
  latestEventPerCamera: Record<string, { type: string; ts: number }>
  kpiHistory: Record<string, number[]>
  funnel: FunnelData
}

export function useLiveData(): LiveDataReturn {
  const [events, setEvents] = useState<StoreEvent[]>([])
  const [sessions, setSessions] = useState<VisitorSession[]>([])
  const [stats, setStats] = useState<LiveStats>(EMPTY_STATS)
  const [queueHistory, setQueueHistory] = useState<QueueSnapshot[]>([])
  const [shelfVisits, setShelfVisits] = useState<Record<string, number>>({})
  const [connected, setConnected] = useState(false)
  const [anomalies, setAnomalies] = useState<AnomalyItem[]>([])
  const [returningProfiles, setReturningProfiles] = useState<ReturningProfile[]>([])
  const [health, setHealth] = useState<HealthData>({ status: 'unknown', stale_feed: false })
  const [eventRate, setEventRate] = useState(0)
  const [latestEventPerCamera, setLatestEventPerCamera] = useState<Record<string, { type: string; ts: number }>>({})
  const [kpiHistory, setKpiHistory] = useState<Record<string, number[]>>(() =>
    Object.fromEntries(KPI_KEYS.map(k => [k, []]))
  )
  const [funnel, setFunnel] = useState<FunnelData>({ entry: 0, zone_visit: 0, billing: 0, purchase: 0 })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const eventTimestamps = useRef<number[]>([])
  const mountedRef = useRef(true)

  const addEvent = useCallback((ev: StoreEvent) => {
    setEvents(prev => [ev, ...prev].slice(0, 50))

    if (ev.zone_id && (ev.event_type === 'ZONE_ENTER' || ev.event_type === 'ZONE_DWELL')) {
      setShelfVisits(prev => ({
        ...prev,
        [ev.zone_id!]: (prev[ev.zone_id!] ?? 0) + 1,
      }))
    }

    const now = Date.now()
    eventTimestamps.current.push(now)
    eventTimestamps.current = eventTimestamps.current.filter(t => now - t < 5000)
    const rate = eventTimestamps.current.filter(t => now - t < 1000).length
    setEventRate(rate)

    if (ev.camera_id) {
      setLatestEventPerCamera(prev => ({
        ...prev,
        [ev.camera_id!]: { type: ev.event_type, ts: now },
      }))
    }
  }, [])

  const updateStats = useCallback((newStats: LiveStats) => {
    setStats(newStats)
    setKpiHistory(prev => {
      const updated = { ...prev }
      KPI_KEYS.forEach(key => {
        const arr = [...(prev[key] ?? []), (newStats as unknown as Record<string, number>)[key] ?? 0]
        updated[key] = arr.slice(-12)
      })
      return updated
    })
  }, [])

  const connectWs = useCallback(() => {
    if (!mountedRef.current) return
    try {
      const url = wsEventsUrl()
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (mountedRef.current) setConnected(true)
      }

      ws.onmessage = (e: MessageEvent) => {
        if (!mountedRef.current) return
        try {
          const data = JSON.parse(e.data as string)
          if (data.type === 'stats') {
            updateStats(data.data as LiveStats)
          } else if (data.event_type) {
            addEvent(data as StoreEvent)
          }
        } catch { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        if (mountedRef.current) {
          setConnected(false)
          wsRef.current = null
          reconnectTimer.current = setTimeout(connectWs, 3000)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch {
      reconnectTimer.current = setTimeout(connectWs, 3000)
    }
  }, [addEvent, updateStats])

  useEffect(() => {
    mountedRef.current = true
    startStreams()
    connectWs()

    return () => {
      mountedRef.current = false
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connectWs])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const s = await fetchStats()
      if (mountedRef.current) updateStats(s)
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [updateStats])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const evs = await fetchEvents(50)
      if (mountedRef.current && !connected) setEvents(evs.slice(0, 50))
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [connected])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const s = await fetchSessions(30)
      if (mountedRef.current) setSessions(s)
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const q = await fetchQueue(30)
      if (mountedRef.current) {
        setQueueHistory(q.slice(-30))
        if (q.length) {
          const latest = q[q.length - 1]
          setStats(prev => ({ ...prev, queue_depth: latest.queue_depth }))
        }
      }
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const data = await fetchAnomalies()
      if (mountedRef.current) setAnomalies(data.anomalies)
    }
    poll()
    const id = setInterval(poll, 12000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const profiles = await fetchReturningCustomers(30)
      if (mountedRef.current) setReturningProfiles(profiles)
    }
    poll()
    const id = setInterval(poll, 8000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const h = await fetchHealth()
      if (mountedRef.current) setHealth(h)
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const poll = async () => {
      if (!mountedRef.current) return
      const f = await fetchFunnel()
      if (mountedRef.current) setFunnel(f)
    }
    poll()
    const id = setInterval(poll, 8000)
    return () => clearInterval(id)
  }, [])

  return {
    events, sessions, stats, queueHistory, shelfVisits,
    connected, anomalies, returningProfiles, health,
    eventRate, latestEventPerCamera, kpiHistory, funnel,
  }
}
