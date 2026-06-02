# DESIGN.md — Store Intelligence System Architecture

> **North Star**: Maximize offline-store conversion-rate accuracy and actionability for real-time operational decision-making.

## 1. System Overview

Store Intelligence is a real-time retail analytics system that ingests anonymized CCTV-derived visitor events and correlates them with POS transactions to compute conversion metrics, detect anomalies, and visualize customer journeys.

### The Problem We Solve

Retail store managers operate blind: they lack real-time visibility into customer behavior patterns (dwell time by zone, queue depth, abandonment rate, conversion drop-off). POS systems tell you what was bought; CCTV tells you the journey. We marry both to answer:

- **Who converted**: Visitors in billing zone within 5 min before a POS transaction
- **What broke**: Queue spiked, conversion dropped 20% vs. 7-day avg, zone has no traffic for 30 min
- **Where to focus**: Heatmap shows dead zones; funnel shows drop-off stage

### High-Level Data Flow

```
┌──────────────────────────┐
│  Raw CCTV Video Clips    │
└──────────────┬───────────┘
               │ (offline, GPU)
     ┌─────────▼──────────┐
     │ Detection Pipeline │
     │ (YOLOv8s + Track)  │
     └────────┬───────────┘
              │
    ┌─────────▼──────────┐
    │ events.jsonl       │
    │ (200+ per store)   │
    └────────┬───────────┘
             │ POST /events/ingest (idempotent)
    ┌────────▼──────────────┐
    │ SQLite EventDB        │
    │ PRIMARY KEY event_id  │
    └────────┬──────────────┘
             │
   ┌─────────▼──────────────────────────────┐
   │ Real-time Computed Metrics             │
   │ • Conversion rate (vs POS txns)         │
   │ • Dwell time per zone                   │
   │ • Queue depth (concurrent BILLING)      │
   │ • Abandonment (entered BILLING, no POS) │
   │ • Anomalies (queue spike, dead zone)    │
   └────────────────────────────────────────┘
             │
             ├──→ GET /metrics (FastAPI)
             ├──→ GET /funnel (session-based)
             ├──→ GET /heatmap (intensity 0–100)
             ├──→ GET /anomalies (open-hours aware)
             └──→ WebSocket live feed (dashboard)
```

## 2. Core Architecture

### 2.1 Event-Driven Schema (Pydantic v2)

**Why an event stream?**

- **Idempotency**: Each event has a UUID; replay is safe via `INSERT OR IGNORE`
- **Auditability**: Full visitor journey visible in logs
- **Scalability**: Easy to stream from multiple cameras; deduplicate at ingestion
- **Actionability**: Anomalies computed on-demand from immutable events

**Event Types** (mutually exclusive, well-ordered):

- `ENTRY` → visitor detected crossing entry threshold → new session start
- `ZONE_ENTER` / `ZONE_EXIT` → visitor motion within zone
- `ZONE_DWELL` → emitted every 30s of continuous zone occupancy (for heatmap)
- `BILLING_QUEUE_JOIN` → visitor detected in billing zone (queue_depth in metadata)
- `BILLING_QUEUE_ABANDON` → visitor left billing without purchasing
- `EXIT` → visitor crosses exit threshold → session end
- `REENTRY` → same visitor_id re-entering within N minutes (high confidence re-ID)

### 2.2 Database Layer (SQLAlchemy 2.0 + SQLite)

```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,  -- UUID v4
    store_id TEXT,
    camera_id TEXT,
    visitor_id TEXT,  -- per-session; resets on EXIT+REENTRY
    event_type TEXT,
    timestamp DATETIME,
    zone_id TEXT,
    dwell_ms INTEGER,
    is_staff BOOLEAN,
    confidence FLOAT,
    metadata TEXT,  -- JSON
    created_at DATETIME
);
CREATE INDEX idx_store_timestamp ON events(store_id, timestamp);
```

**Why SQLite for MVP?**

- Zero DevOps overhead (single file, no Postgres setup)
- ACID guarantees (critical for idempotency)
- SQL familiar to ops teams
- Works offline (valuable for edge deployment)

**Idempotency via PRIMARY KEY**: `INSERT OR IGNORE event_id` ensures re-playing events.jsonl 10× yields identical state. No dedup logic needed in application.

**Scaling bottleneck at 40 stores**: SQLite single-writer; contention limit ~3–5 concurrent writes. See CHOICES.md for migration strategy.

### 2.3 Metrics Computation (Real-time, On-Demand)

#### Unique Visitors

```sql
SELECT COUNT(DISTINCT visitor_id) WHERE event_type = 'ENTRY' AND is_staff = false
```

**Why**: Entry is the beginning of a session; visitor_id resets on new sessions.

#### Conversion Rate

```
converted = COUNT(DISTINCT visitor_id) WHERE visitor_id IN (
    SELECT visitor_id FROM events
    WHERE zone_id = 'BILLING' AND timestamp BETWEEN txn.timestamp - 5min AND txn.timestamp
)
rate = converted / unique_visitors
```

**Why 5-minute window?** Retail norms: customer queues for ~3–5 min before transaction. Window large enough to catch queues, small enough to avoid attributing conversions to unrelated future sales.

**Why time-window + store_id only?** No customer_id in POS data; temporal proximity is the signal.

#### Queue Depth (Concurrent Occupancy)

```
active = COUNT(DISTINCT visitor_id) WHERE (
    BILLING_QUEUE_JOIN in last 10 min
    AND NO EXIT or BILLING_QUEUE_ABANDON after join
)
```

**Why**: Real-time queue length is operational metric for staffing decisions.

#### Abandonment Rate

```
billing_visitors = COUNT(DISTINCT visitor_id) WHERE zone_id = 'BILLING'
abandoned = COUNT(visitor_id) WHERE NO POS txn within 5 min of billing enter
rate = abandoned / billing_visitors
```

**Why**: High abandonment = friction in checkout (long queue, unfriendly staff, payment issues).

#### Heatmap (Zone Intensity)

```
visit_count[zone] = COUNT(ZONE_ENTER per zone)
avg_dwell[zone] = AVG(dwell_ms for ZONE_DWELL per zone)
intensity[zone] = 100 * visit_count / max(visit_count)
```

**Why 0–100?** Normalized for rendering on a grid; easy for dashboard to color-code.

### 2.4 Anomaly Detection (Open-Hours Aware)

All anomalies check `store_layout.open_hours` before firing; never alert for closed stores.

#### Queue Spike

- Current queue depth > max(historical avg × 1.5, 5 concurrent visitors)
- **Action**: "Increase checkout staff"

#### Conversion Drop

- Today's rate < 7-day avg × 0.8 (20% drop)
- Requires ≥50 entries in week (else "insufficient history")
- **Action**: "Review merchandising and checkout experience"

#### Dead Zone

- No ZONE_ENTER in zone for 30+ minutes while store is open
- **Action**: "Check zone visibility or re-arrange stock"

## 3. AI-Assisted Decisions

### Decision 1: Tracker Split (ByteTrack vs BoT-SORT)

**What AI suggested**: "Use ByteTrack for all clips; it's state-of-the-art and faster."

**What I chose**: ByteTrack for entry/floor, BoT-SORT for billing.

**Why I overrode**:

- Entry/floor cameras have open space, fast motion → ByteTrack excels (low-conf recovery)
- Billing camera has **heavy occlusion** (queue bunching, checkout counter blocking): appearance embeddings from BoT-SORT hold IDs through occlusion; ByteTrack would lose IDs, create phantom enters
- This is the **single most defensible CV choice**: documented in CHOICES.md with VLM rationale

### Decision 2: Idempotent Ingest (SQLite PRIMARY KEY)

**What AI suggested**: "Use a dedup table with event_id + hash; implement in application code."

**What I chose**: SQLite PRIMARY KEY on event_id → `INSERT OR IGNORE` (zero dedup code).

**Why I overrode**:

- Simpler, fewer bugs, zero application logic
- Atomic; leverages DB ACID guarantees
- **Scaled to 40 stores**: Replace SQLite with Postgres; same `INSERT … ON CONFLICT DO NOTHING` pattern

### Decision 3: Open-Hours Awareness for Anomalies

**What AI suggested**: "Fire anomalies 24/7; let ops team filter."

**What I chose**: Dead zone / conversion drop only fire during store open hours; queue spike fires anytime.

**Why I overrode**:

- Reduces false CRITICALs at night (on-call engineer won't need to wake up for a closed store)
- North Star: actionability. Dead zone at 3 AM is not actionable.

## 4. Production Readiness

### 4.1 Structured Logging

Every request logs:

```json
{
  "trace_id": "uuid",
  "method": "POST",
  "path": "/events/ingest",
  "status_code": 200,
  "latency_ms": 125,
  "store_id": "STORE_BLR_002",
  "event_count": 150,
  "timestamp": "2026-03-03T14:22:10Z"
}
```

**Why**: On-call engineer can grep logs by trace_id, see full request context without asking.

### 4.2 Graceful Degradation

Database unavailable → HTTP 503 + structured JSON body:

```json
{
  "error": "database_unavailable",
  "message": "Database service is temporarily unavailable",
  "trace_id": "..."
}
```

**Never** returns raw Python stack traces. Safe to expose to dashboards.

### 4.3 CPU-Only Runtime

- Scored runtime (`docker compose up`) runs on CPU
- GPU used **only** for offline detection pipeline (Colab/Kaggle free T4)
- Reviewers can run on clean machine without GPU

## 5. Scaling Path

```
TODAY (1–5 stores)        TOMORROW (40 stores)
SQLite                    Postgres
Single process            Horizontal API workers (K8s)
File-based DB             Persistent volumes
No caching                Redis cache layer (metrics)
                          Redis Streams / Kafka (event stream)
```

## 6. Edge Case Handling

### 6.1 Re-Entry Deduplication

**Problem**: Same customer enters store 3 times in 2 hours. Should count as 1 or 3 unique visitors?

**Solution**:

- Appearance-based re-ID (BoT-SORT embeddings) matches exiting customer to re-entering person
- Same `visitor_id` assigned across multiple ENTRY events
- Metrics count unique `visitor_id`, not total ENTRY events
- Result: 1 unique visitor, accurate conversion rate

**Implementation**:

```python
# In detect.py: re-ID tracker maintains 15-minute window
matched_visitor_id, sim = reid.match_reentry(crop, now_epoch)
if matched_visitor_id and sim >= 0.7:
    is_reentry = True
    visitor_id = matched_visitor_id
else:
    is_reentry = False
    visitor_id = f"VIS_{track_id}_{int(now_epoch)}"
```

**Test coverage**: `test_edge_cases.py::TestReEntryDeduplication`

### 6.2 Staff Exclusion

**Problem**: Staff move through store constantly. Should they inflate metrics?

**Solution**:

- Spatial polygon detection: if bbox centroid inside `STAFF_ZONE_POLYGON` → staff
- All metrics queries filter `is_staff = false`
- Queue depth calculation excludes staff (billing zone only)
- Result: Accurate customer-only metrics

**Implementation**:

```python
# In detect.py
staff_conf = is_staff_vit(
    person_crop=crop,
    bbox=(x1c, y1c, x2c, y2c),
    clip_type=clip_type,
    staff_zone_polygon=STAFF_ZONE_POLYGON
)
is_staff = staff_conf > 0.5

# In compute_metrics()
events = db.query(EventDB).filter(
    and_(
        EventDB.is_staff == False,
        ...
    )
).all()
```

**Test coverage**: `test_edge_cases.py::TestStaffDetection`

### 6.3 Group Entry

**Problem**: 5 family members walk in together. Is that 1 entry or 5?

**Solution**:

- YOLO detects each person independently → 5 track IDs
- Each person gets an individual ENTRY event
- Funnel counts 5 separate sessions
- Business rationale: POS has 5 potential buyers, not 1 group buyer
- Result: Accurate conversion rate (1 purchase / 5 entries = 20%)

**Trade-off**: Slightly underestimates family dynamics, but correct for business metrics.

**Implementation**:

```python
# In detect.py: one ENTRY event per track_id
for track_id in ids:
    event_dict = emitter.emit(
        track_id=int(track_id),
        visitor_id=f"VIS_{track_id}_{int(now_epoch)}",
        event_type="ENTRY",
        ...
    )
```

**Test coverage**: `test_edge_cases.py::TestGroupEntry`

### 6.4 Occlusion (Billing Queue)

**Problem**: Checkout counter blocks customers; trackers lose ID, create phantom entries.

**Solution**: BoT-SORT with appearance embeddings maintains ID through occlusion:

- Stores per-frame appearance representation
- Matches on both motion + appearance (not motion alone)
- Result: Correct queue depth even with significant occlusion

**Why not ByteTrack?** ByteTrack relies on spatial proximity in consecutive frames; occlusion breaks that chain.

### 6.5 Abandonment (Entered Billing, No Purchase)

**Problem**: Customer joins queue but leaves without buying. How to detect?

**Solution**:

- BILLING_QUEUE_JOIN on zone_id='BILLING' entry
- ZONE_EXIT on billing exit
- If ZONE_EXIT but NO POS transaction within 5 min → abandonment
- Abandonment_rate = abandoned / total_billing_visits

**Implementation**:

```python
abandoned = count(
    visitor_id
    WHERE zone_id='BILLING'
    AND timestamp(zone_exit) > timestamp(zone_enter)
    AND NOT EXISTS (
        SELECT 1 FROM pos_txns
        WHERE timestamp BETWEEN zone_enter - 5min AND zone_exit + 5min
    )
)
abandonment_rate = abandoned / billing_visits
```

**Test coverage**: `test_edge_cases.py::TestBillingQueueAbandonment`

### 6.6 Low-Confidence Detections

**Problem**: YOLO model returns 0.55-conf detection. Is it a person or noise?

**Solution**:

- Pass confidence through as-is (never suppress)
- Flag in metadata if conf < 0.7
- Metrics include all detections (graceful degradation)
- Heatmap marks zones as "unconfirmed" if avg conf < 0.7
- Result: Better than deleting signal; ops team sees confidence levels

**Why not suppress?** Suppression loses information. Two 0.55-conf detections 0.5s apart might be same person flickering; don't delete both.

### 6.7 Zero-Traffic Graceful Degradation

**Problem**: Empty store; no events. What should /metrics return?

**Solution**:

```python
if not events:
    return MetricsResponse(
        unique_visitors=0,
        conversion_rate=0.0,
        abandonment_rate=0.0,
        current_queue_depth=0,
        ...
    )
```

**Never** NaN, null, or None. Always a valid response.

**Test coverage**: `test_edge_cases.py::test_metrics_empty_store`

### 6.8 Output Variation (Anti-Hardcoding)

**Problem**: Reviewer wants to verify system is not hardcoded. How to prove?

**Solution**: Test harness adds varying numbers of events and confirms outputs scale:

```python
# 0 events → unique_visitors = 0
# 5 events → unique_visitors = 5
# 15 events → unique_visitors = 15
```

Outputs must vary with input; no fixed responses.

**Test coverage**: `test_edge_cases.py::TestOutputVariation`

## 7. Testing Strategy

- **>70% coverage**: unit tests for metrics, funnel, anomalies, ingestion
- **Acceptance gate (assertions.py)**: 10 end-to-end tests on live API
- **Edge case tests (test_edge_cases.py)**: 40+ scenarios (re-entry, staff, groups, abandonment, etc.)
- **Idempotency tests**: same payload twice → same state
- **Zero-traffic tests**: metrics never crash or return NaN
- **Output variation tests**: confirm metrics scale with input (anti-hardcoding)

## Summary

Store Intelligence trades off some scalability (SQLite) for simplicity and determinism. Every design decision is defensible against the North Star: **conversion-rate accuracy and operational actionability**.

**Edge cases are not afterthoughts**: re-entry deduplication, staff exclusion, group handling, queue occlusion, and abandonment are baked into the core design. Structured tests verify correctness.

The API is production-hardened (structured logging, graceful degradation, >70% tests), and the detection pipeline is decoupled (offline, GPU-optional).
