import { useLiveData } from './hooks/useLiveData'
import { Header } from './components/Header'
import { KPICommandBar } from './components/KPICommandBar'
import { CameraWall } from './components/CameraWall'
import { CustomerFlowFunnel } from './components/CustomerFlowFunnel'
import { LiveEventStream } from './components/LiveEventStream'
import { ShelfZoneHeatmap } from './components/ShelfZoneHeatmap'
import { QueueGauge } from './components/QueueGauge'
import { ReturningCustomers } from './components/ReturningCustomers'
import { SessionTable } from './components/SessionTable'
import { AnomalyToast } from './components/AnomalyToast'
import { AnomalyPanel } from './components/AnomalyPanel'

export default function App() {
  const {
    events,
    sessions,
    stats,
    queueHistory,
    shelfVisits,
    connected,
    anomalies,
    returningProfiles,
    health,
    eventRate,
    latestEventPerCamera,
    kpiHistory,
    funnel,
  } = useLiveData()

  const activeCount = sessions.filter(s => !s.is_staff && s.status === 'active').length

  return (
    <div className="app-shell">
      <Header connected={connected} health={health} eventRate={eventRate} />
      <AnomalyToast anomalies={anomalies} />

      <KPICommandBar stats={stats} kpiHistory={kpiHistory} />

      <main className="workspace">
        <div className="content-grid">
          {/* LEFT COLUMN */}
          <div className="main-column">
            <section className="card animate-in">
              <div className="card-header">
                <span className="card-title">Live Camera Feeds</span>
                <span
                  className="card-meta"
                  style={{ color: connected ? 'var(--live)' : 'var(--text-muted)' }}
                >
                  {connected ? '● STREAMING' : '● CONNECTING'}
                </span>
              </div>
              <div className="card-body">
                <CameraWall stats={stats} latestEventPerCamera={latestEventPerCamera} />
              </div>
            </section>

            <div className="analytics-row animate-in">
              <section className="card">
                <div className="card-header">
                  <span className="card-title">Shelf Zone Activity</span>
                  <span className="card-meta">live</span>
                </div>
                <div className="card-body">
                  <ShelfZoneHeatmap visits={shelfVisits} events={events} />
                </div>
              </section>

              <section className="card">
                <div className="card-header">
                  <span className="card-title">Billing Queue</span>
                  <span
                    className="card-meta"
                    style={{
                      color: stats.queue_depth >= 7 ? 'var(--exit-red)' :
                             stats.queue_depth >= 4 ? 'var(--warn)' :
                             'var(--live)',
                    }}
                  >
                    depth {stats.queue_depth}
                  </span>
                </div>
                <div className="card-body">
                  <QueueGauge depth={stats.queue_depth} history={queueHistory} />
                </div>
              </section>

              <section className="card">
                <div className="card-header">
                  <span className="card-title">Alerts</span>
                  <span
                    className="card-meta"
                    style={{ color: anomalies.length ? 'var(--warn)' : 'var(--live)' }}
                  >
                    {anomalies.length ? `${anomalies.length} active` : 'nominal'}
                  </span>
                </div>
                <div className="card-body">
                  <AnomalyPanel anomalies={anomalies} />
                </div>
              </section>
            </div>

            <section className="card animate-in">
              <div className="card-header">
                <span className="card-title">Visitor Sessions</span>
                <span className="card-meta">{activeCount} active</span>
              </div>
              <div className="card-body" style={{ padding: 0 }}>
                <SessionTable sessions={sessions} />
              </div>
            </section>
          </div>

          {/* RIGHT COLUMN */}
          <div className="side-column">
            <section className="card animate-in">
              <div className="card-header">
                <span className="card-title">Customer Flow</span>
                <span className="card-meta">
                  {funnel.entry > 0
                    ? `${Math.round((funnel.purchase / funnel.entry) * 100)}% conv.`
                    : 'funnel'}
                </span>
              </div>
              <div className="card-body">
                <CustomerFlowFunnel funnel={funnel} />
              </div>
            </section>

            <section className="card animate-in">
              <div className="card-header">
                <span className="card-title">Live Events</span>
                <span className="card-meta">{events.length} recent</span>
              </div>
              <div className="card-body" style={{ padding: '6px 0' }}>
                <LiveEventStream events={events} />
              </div>
            </section>

            <section className="card animate-in">
              <div className="card-header">
                <span className="card-title">Returning Customers</span>
                <span
                  className="card-meta"
                  style={{
                    color: returningProfiles.length ? 'var(--returning)' : 'var(--text-muted)',
                    fontWeight: returningProfiles.length ? 500 : 400,
                  }}
                >
                  ↩ {returningProfiles.length}
                </span>
              </div>
              <div className="card-body">
                <ReturningCustomers profiles={returningProfiles} latestEvent={events[0]} />
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  )
}
