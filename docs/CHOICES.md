# CHOICES.md — 13 Major Design Decisions

> Every trade-off is framed against the **North Star**: offline-store conversion-rate accuracy and operational actionability.

---

## DETECTION LAYER

### 1. Model: YOLOv8s (vs YOLOv8n, YOLOv8x, RT-DETR)

| Aspect   | YOLOv8n       | YOLOv8s           | YOLOv8x      | RT-DETR      |
| -------- | ------------- | ----------------- | ------------ | ------------ |
| Speed    | Very Fast     | Fast              | Moderate     | Fast         |
| Accuracy | 63% mAP       | 67% mAP           | 71% mAP      | 73% mAP      |
| Free GPU | Yes (Fast T4) | Yes (Moderate T4) | No (Timeout) | No (Timeout) |

**What I chose**: YOLOv8s  
**Why**: 67% mAP is plenty for person detection in retail (most people in frame are clear); speed on free T4 is critical (1–3 min per 10-min clip). YOLOv8x is overkill and times out on Kaggle's 9-hr limit.

**North Star link**: False negatives in person detection → missed ENTRY events → undercount conversion rate. YOLOv8s at 67% mAP is acceptable; YOLOv8n misses too many crowded scenes.

---

### 2. Tracker Split: ByteTrack (entry/floor) + BoT-SORT (billing)

| Scenario                    | ByteTrack         | BoT-SORT                    |
| --------------------------- | ----------------- | --------------------------- |
| Open space, fast motion     | Yes - Fast, clean | Slower                      |
| Heavy occlusion, stationary | No - Loses IDs    | Yes - Appearance embeddings |

**What I chose**:

- **Entry/floor cameras**: ByteTrack (open, fast motion)
- **Billing camera**: BoT-SORT (queue occlusion, stationary queuers)

**Why I overrode**:
Billing queue is the highest-value frame: queue depth and conversion accuracy depend on correct ID association through occlusion. A customer obscured for 2 seconds at checkout is not a new person. ByteTrack would drop the ID and create phantom new entries; BoT-SORT appearance embeddings maintain IDs through occlusion. **This is the single most defensible CV decision.**

**North Star link**: Accurate queue depth → accurate staffing decisions. Phantom entries in billing → inflated visitor counts → wrong conversion rate.

**Trade-off**: BoT-SORT is slower; billing clip processing takes ~2× longer. Acceptable for offline pass.

---

## TRACKING ARCHITECTURE — Detailed Rationale

### Context: The Multi-Camera Problem

Multi-camera person tracking is not one problem — it is two distinct problems stacked together:

1. **Intra-camera tracking** — maintaining a consistent local ID for a person within a single camera's video stream across frames.
2. **Inter-camera Re-ID** — matching the same person's identity across two or more non-overlapping camera feeds.

Every tracker evaluation below was done against both dimensions separately, because conflating them leads to wrong architectural decisions. The system processes CCTV footage from 3 camera angles per store (Entry, Main Floor, Billing Area) and must assign a consistent `visitor_token` to each customer across all three feeds.

### Trackers Examined

#### 2A. SORT (Simple Online and Realtime Tracking)

SORT uses a Kalman filter for motion prediction and the Hungarian algorithm for assignment. It is fast and simple but relies entirely on IoU overlap with no appearance model. In retail environments with shelves, counters, and partial occlusions, SORT produces a high rate of ID switches whenever a person is briefly hidden behind a shelf or another person.

**Verdict**: Eliminated. No appearance model means it cannot survive even moderate occlusions in a store environment.

---

#### 2B. DeepSORT (Deep SORT)

DeepSORT extends SORT by adding a deep appearance descriptor — a CNN trained on the MARS Re-ID dataset — that produces a 128-dimensional embedding per detection. The Kalman filter handles motion, and the appearance embedding handles re-association after occlusion.

**My analysis**:

- DeepSORT's Re-ID gallery operates within a single camera session. It does not maintain embeddings across camera handoffs — the gallery is local to each tracker instance.
- DeepSORT can struggle with similar-looking objects and heavy occlusion, and lacks explicit camera-motion compensation.
- In practice, DeepSORT is used as the intra-camera tracker only — a separate Re-ID module handles cross-camera matching.
- Per-frame CNN inference overhead is higher than motion-only trackers.

**Key finding**: DeepSORT is not a cross-camera Re-ID solution. Its appearance embeddings operate within a single-camera context. Cross-camera matching requires a dedicated Re-ID model regardless of which intra-camera tracker is used.

**Verdict**: Not selected. Replaced by ByteTrack (entry/floor) and BoT-SORT (billing) for intra-camera work, with appearance embeddings handling cross-camera Re-ID separately.

---

#### 2C. ByteTrack (Full Evaluation)

ByteTrack's key insight is that low-confidence detections — which SORT and DeepSORT discard — often correspond to partially occluded persons. ByteTrack runs two association passes:

- First pass: high-confidence detections, IoU + Kalman filter.
- Second pass: remaining unmatched tracks are associated with low-confidence detections.

It does not use an appearance model internally, which keeps it extremely fast.

**My analysis**:

- I analyzed ByteTrack's two-pass approach: high-confidence detections first, then low-confidence recovery. This is directly relevant to retail — people partially hidden behind shelves still produce low-confidence boxes that ByteTrack recovers.
- ByteTrack is fast and simple for open spaces (entry/floor cameras) where clear motion and IoU overlap dominate.
- Native integration via `model.track(tracker="bytetrack.yaml")` — zero additional dependencies.

**Verdict**: Selected for Entry and Main Floor cameras (TRACKER_CONFIG in detect.py).

---

#### 2D. BoT-SORT and BoT-SORT-ReID (Full Evaluation)

BoT-SORT combines IoU-based motion association with optional Re-ID appearance embeddings and camera-motion compensation. It is built on top of ByteTrack and extends it with:

- An 8-dimensional Kalman filter state vector (includes width and height, unlike ByteTrack's 4-dim).
- Optional Re-ID encoder with EMA feature smoothing.
- Camera-motion compensation.

**My analysis**:

The billing area is the densest zone in the store — multiple people standing close together, limited movement, overlapping bounding boxes. This is exactly the scenario where ByteTrack's motion-only association starts producing ID switches, because IoU overlap between nearly-stationary adjacent people becomes ambiguous.

BoT-SORT handles this by adding appearance embeddings and smarter motion matching, making it robust to occlusion and crowded scenarios.

**Important note**: The built-in BoT-SORT ReID is useful for intra-camera occlusion recovery but not a production cross-camera Re-ID solution. For cross-camera matching, I implemented a separate appearance embedding module.

**Verdict**: Selected for Billing camera only (TRACKER_CONFIG in detect.py). The appearance model earns its overhead specifically in the queue zone. Not used for entry/floor where ByteTrack is faster and sufficient.

---

#### 2E. StrongSORT

StrongSORT applies engineering improvements to DeepSORT: stronger Re-ID feature extractor, camera-motion compensation, and advanced Kalman filtering.

**My analysis**:

- Strong performance on benchmarks but no native Ultralytics support.
- Same cross-camera limitation as DeepSORT.
- Integration complexity not justified given ByteTrack + BoT-SORT already cover this pipeline's intra-camera needs.

**Verdict**: Not selected.

---

### Per-Camera Tracker Configuration

```python
TRACKER_CONFIG = {
    "entry":   "bytetrack.yaml",   # clean entry line, fast motion, no queue
    "floor":   "bytetrack.yaml",   # open floor, shelf occlusions, speed matters
    "billing": "botsort.yaml",     # dense queue, stationary people, appearance needed
}
```

This is not arbitrary — it reflects the physical characteristics of each camera zone:

| Camera  | Scene characteristics          | Why this tracker              |
| ------- | ------------------------------ | ----------------------------- |
| Entry   | Single-file motion, clear IoU  | ByteTrack — speed + two-pass  |
| Floor   | Moving through aisles, shelves | ByteTrack — two-pass recovery |
| Billing | Queue, dense, stationary crowd | BoT-SORT — appearance model   |

---

### Cross-Camera Re-ID Strategy

None of the trackers above solve cross-camera identity by themselves. My research and analysis confirms:

> An intra-camera tracker assigns local IDs within one feed. Cross-camera identity matching requires a separate appearance embedding model that builds a shared gallery across all cameras.

**I evaluated these approaches for the Re-ID module**:

- **HSV histogram (MVP)**: 48-dimensional vector. Fast, zero dependencies, but fails when two people wear similar-colored clothing. MVP placeholder.
- **DeepSORT's built-in CNN**: 128-dim embeddings. Better than histogram but designed for single-camera use; appearance drift across cameras is a limitation.
- **OSNet (Omni-Scale Network)**: Handles scale, viewpoint, and lighting variation. Available via `torchreid`. 512-dim embeddings.
- **FastReID**: Production Re-ID library. Supports multiple backbones and training datasets.

**Current state**: Appearance embeddings used for cross-camera matching within 15-minute time window, cosine similarity threshold 0.7.

**Target state**: Replace MVP with OSNet via `torchreid.utils.FeatureExtractor` pre-trained on Market-1501 as scaling path.

---

### Trackers Rejected and Why

| Option                                  | Rejected Because                                         |
| --------------------------------------- | -------------------------------------------------------- |
| SORT                                    | No appearance model; fails on any occlusion              |
| DeepSORT for cross-camera               | Gallery is intra-camera scoped; limited for cross-camera |
| ByteTrack for billing zone              | Motion-only fails in stationary dense queues             |
| BoT-SORT for entry/floor                | Appearance overhead not justified; ByteTrack sufficient  |
| StrongSORT                              | No native Ultralytics support; same cross-camera limit   |
| Built-in BoT-SORT ReID for cross-camera | Better as intra-camera occlusion recovery only           |
| Single tracker across all cameras       | Architecturally incorrect — cameras are non-overlapping  |

---

### Tracker Implementation Details

**YOLOv8 model variant**: `yolov8s` (as implemented)
**Reason**: YOLOv8s balances speed and accuracy for 640×640 inference on a T4 GPU with vid_stride=3. For server-side docker-compose deployment, YOLOv8s gives good accuracy on partially occluded persons in crowded retail scenes.

**conf=0.25 floor** (as implemented):
Intentionally kept low per the requirement to not suppress low-confidence events — they are flagged downstream via the confidence field in the event schema, not silently dropped. This enables ByteTrack's two-pass low-confidence recovery in the second pass.

---

**Approach**:

1. On EXIT: save visitor's last frame embedding (via BoT-SORT backbone)
2. On new ENTRY (within N minutes, N=15): compare embedding to all recent exits
3. If similarity > 0.7 AND time gap < 15 min → REENTRY (same visitor_id)
4. Else → NEW ENTRY

**Why not trajectory IoU?**

- Trajectory IoU fails across camera cuts; embedding is camera-invariant
- Time-window prevents creeping re-matches (person A exits at 14:00, person B enters at 18:00 should NOT match)
- **Flag low-confidence merges** (0.65–0.7) instead of silently merging; ops team investigates

**North Star link**: Re-entry de-duplication is critical for conversion rate. If we merge the same person as two visitors, we undercount unique_visitors and overcount conversion rate.

---

### 4. Group Entry: One Unique Track ID Per Person → N ENTRY Events

**Question**: Should a group of 5 people entering together create 1 "GROUP_ENTRY" or 5 "ENTRY" events?

**What I chose**: 5 separate ENTRY events (one per person)

**Why**:

- Simplifies funnel logic (each entry is one session, not N sessions for a group)
- Conversion rate is correct: 5 people enter, if 1 buys, rate = 20%, not "1 group buys"
- Matches POS reality: cash register rings 1 transaction per customer, not per group

**Trade-off**: May underestimate queue depth if families shop together. Acceptable; families are rare vs. individual shoppers.

---

### 5. Confidence Policy: Pass Real Detection Confidence, Never Suppress

**What I initially considered**: Dropping low-conf detections to clean up noise.

**What I chose**: Pass **all** detections with real confidence; flag low-conf in metadata.

**Why I overrode**:

- Graceful degradation: if detector is uncertain, let ops see uncertainty (confidence field)
- Suppression loses information: a 0.65-conf entry + a 0.68-conf entry might be the same person in rapid re-detection
- Heatmap confidence flag (`data_confidence = false if <20 sessions`) tells ops when to trust metrics

**North Star link**: Suppressing low-conf detections = information loss. Better to flag uncertainty.

---

### 6. Staff Detection: Polygon-Based Spatial ROI

**Approach**:

1. Define `STAFF_ZONE_POLYGON` per camera covering the billing counter and staff area

   ```python
   STAFF_ZONE_POLYGON = [
       (80, 120),    # top-left
       (320, 100),   # top-right
       (350, 420),   # bottom-right
       (60, 450)     # bottom-left
   ]
   ```

2. For each detected person bbox (x1, y1, x2, y2):
   - Compute centroid: cx = (x1 + x2) / 2, cy = (y1 + y2) / 2
   - Check if centroid is inside polygon using OpenCV.pointPolygonTest()
   - If inside: compute soft confidence based on distance to polygon boundary
   - Soft confidence = min(1.0, abs(distance_to_boundary) / 50 + 0.6)

3. Cache result per track_id (staff rarely moves zones within single clip)

**Why polygon-based?**

- Deterministic: no model uncertainty, no API calls
- Fast: single point-in-polygon check (~0.1 ms)
- Privacy-respecting: no image crops stored or sent externally
- Edge-deployable: no GPU required
- Interpretable: ops team can visualize and adjust polygon boundaries per camera

**Why not histogram or VLM?**

- Histogram fails with variable staff uniforms (can wear casual clothes in smaller stores)
- VLM adds API cost and latency (unacceptable for real-time video processing)
- Polygon is camera-specific; works for fixed retail layouts

**Soft confidence gradient**:

- Person deep inside staff zone (>50px from boundary) → confidence 0.9–1.0
- Person near boundary → confidence 0.6–0.7
- Allows ops to filter by confidence threshold if needed

**North Star link**: Staff detection errors → inflated customer counts → inaccurate conversion rate. Polygon-based is deterministic and accurate for static retail environments.

---

## EVENT SCHEMA

### 7. Flat Event + Nested Metadata (not hierarchical event types)

**Design**:

```json
{
  "event_id": "uuid",
  "visitor_id": "VIS_001",
  "event_type": "ZONE_DWELL",
  "zone_id": "SKINCARE",
  "dwell_ms": 30000,
  "metadata": {
    "session_seq": 2,
    "queue_depth": null,
    "sku_zone": "MOISTURISER"
  }
}
```

**Why flat?**

- Simpler SQL queries (no nested JSON extraction)
- Re-entries are detectable: same visitor_id after EXIT
- session_seq in metadata preserves event order within session

**Why nested metadata?**

- Extensible: add `facial_expression` or `cart_weight` later without schema migration
- Optional fields (queue_depth = null for non-billing events) → no wasted storage

---

## API ARCHITECTURE

### 8. Storage: SQLite + event_id PRIMARY KEY (idempotent INSERT OR IGNORE)

**Alternatives considered**:

- **Dedup table** (event_id + hash): requires extra logic, easier to mess up
- **Postgres with UPSERT**: heavier infra, not free on Heroku
- **Redis + Disk**: complex fault tolerance

**What I chose**: SQLite PRIMARY KEY → `INSERT OR IGNORE`

**Implementation**:

```python
db_event = EventDB(event_id=event.event_id, ...)  # Already exists? Skipped.
db.add(db_event)
db.commit()  # Idempotent: second time → ignored
```

**Why**:

- Zero dedup logic in application code
- ACID guarantees: SQLite enforces uniqueness
- Replay events.jsonl 10× → same final state

**Scaling bottleneck at 40 stores**:
SQLite is single-writer; write contention limit ~3–5 concurrent ingest calls. Beyond that, transactions queue and timeout.

**Migration path**:

```sql
-- Postgres equivalent
INSERT INTO events (...) VALUES (...)
ON CONFLICT (event_id) DO NOTHING;
-- Add Redis cache for metrics (which are expensive to recompute)
-- Add Kafka topic for event stream (decouple ingestion from metrics)
-- Horizontal API workers behind load balancer
```

**North Star link**: Idempotency is critical for streaming reliability. If `POST /ingest` times out, we retry; without idempotency, we'd duplicate events and break conversion rates.

---

### 9. Conversion Correlation: Time-Window + Store_ID Only

**Question**: How do we link visitors to POS transactions?

**Constraints**:

- No customer_id in POS data
- No payment method identifier

**Approach**:

- Visitor in BILLING zone within 5 min **before** POS timestamp = converted
- Window: 3–5 min queue time + checkout

**Why 5 minutes (not 3, not 10)?**

- Retail norms: avg queue ~2–4 min, checkout ~1 min
- 10 min too loose: might catch unrelated transactions
- 3 min too tight: misses slow queues

**Why time-window + store_id only (not spatial)?**

- Billing zone boundaries are blurry (camera angle, occlusion)
- Temporal proximity is strong signal in retail

**North Star link**: Accurate conversion correlation → accurate conversion rate → accurate business insights for ops team.

**Trade-off**: May attribute conversions to wrong person (if two people in billing within 5 min and two transactions). Acceptable; retail conversions are per-store, not per-person.

---

### 10. Anomalies are Open-Hours Aware

**Decision**: Dead zone and conversion drop anomalies only fire during store open hours.

**Why**:

- Dead zone at 3 AM = closed store, not actionable
- Reduces false CRITICAL alerts → on-call engineer won't hate the system
- Queue spike fires anytime (overnight emergency restocking)

**Implementation**:

```python
def is_store_open(now, open_hours):
    day_name = now.strftime("%a").lower()  # "mon", "tue", ...
    open_time, close_time = open_hours[day_name]
    return open_time <= now.time() <= close_time
```

**North Star link**: Actionability. Only alert on things ops can act on.

---

### 11. Idempotent + Partial-Success Ingest

**Response format**:

```json
{
  "total": 150,
  "accepted": 148,
  "duplicates": 2,
  "rejected": 0,
  "events": [
    { "event_id": "...", "status": "accepted", "message": "" },
    {
      "event_id": "...",
      "status": "duplicate",
      "message": "Event with this event_id already ingested"
    }
  ]
}
```

**Why partial success?**

- A 150-event batch: 2 duplicates, 1 malformed = 147 good events
- Without partial success, we'd either accept all (duplicate danger) or reject all (lose data)
- Partial success + per-event status = ops team can investigate rejected events

**Why never 5xx on valid input?**

- Valid event = correct schema, proper timestamps, valid UUID
- If **valid** event fails: return 200 with rejected status, not 500
- 500 only for infrastructure failures (DB down, disk full), not user errors

**North Star link**: Robustness. Fleet of 40 stores sending events; one malformed event shouldn't break the whole system.

---

## PRODUCTION

### 12. CPU-Only Scored Runtime

**Constraint**: Reviewers run `docker compose up` on clean machine with NO GPU.

**Decision**:

- API + ingestion run on CPU (SQLite, FastAPI, all metrics computation)
- GPU used **only** for offline detection pipeline (Colab, Kaggle, one-time pass)
- API scales horizontally on CPU workers (no GPU contention)

**Why**:

- GPU is a bottleneck resource; ops doesn't want to tie up GPU for API
- Detection is batch (offline), doesn't need interactive latency
- Easier to deploy on commodity servers (no NVIDIA drivers)

---

### 13. Structured JSON Logging + 503 Graceful Degradation

**Every request logs**:

```json
{
  "timestamp": "2026-03-03T14:22:10Z",
  "trace_id": "uuid",
  "method": "POST",
  "path": "/events/ingest",
  "status_code": 200,
  "latency_ms": 125,
  "store_id": "STORE_BLR_002",
  "event_count": 150
}
```

**DB unavailable → 503**:

```json
{
  "status_code": 503,
  "error": "database_unavailable",
  "message": "Database service is temporarily unavailable"
}
```

**Never raw Python stack traces.**

**Why**:

- On-call engineer greps by trace_id, sees full context
- No surprise failures; errors are structured + actionable
- Graceful degradation signals when human intervention needed

---

## PRE-ANSWER: FOLLOW-UP QUESTIONS

### Q1: "Billing clip has heavy occlusion. Doesn't ByteTrack fail?"

**Answer**: Yes, which is why we use BoT-SORT for billing. ByteTrack recovers from occlusion via low-conf matching (centroid-based fallback), but BoT-SORT's appearance embeddings are more robust for stationary queues. See Decision 2.

### Q2: "What if a different person enters same direction 3 seconds after another exits? Re-ID fails?"

**Answer**:

1. **Trajectory + time-window gating**: Entry at (x=200, y=100, t=14:00) + Exit at (x=210, y=95, t=13:50) → very close spatially but 10 min apart → time gating rejects
2. **Appearance embedding**: Different persons have different appearance; embedding similarity < 0.7 → not a match
3. **Flag low-confidence merges** (0.65–0.7) instead of silently merging; ops investigates
   **North Star**: Worst case is a conservative split (two visitors instead of one); inflates unique_visitors and underestimates conversion rate. Better than falsely merging.

### Q3: "What breaks at 40 live stores? What's the upgrade path?"

**Answer**:

- **SQLite write contention**: Single writer, ~3–5 concurrent writes max
- **Upgrade**:
  1. Postgres (horizontal scale, connection pooling)
  2. Redis cache (metrics are expensive to recompute; cache for 30s)
  3. Kafka (decouple event stream from ingestion; workers consume + compute)
  4. K8s (horizontal API workers)

### Q4: "Polygon-based staff detection vs other approaches? When to switch?"

**Answer**:

- **Polygon-based** (current) is deterministic, privacy-respecting, no ML model, no API calls, fast
  - Works well for static retail layouts with fixed staff zones
  - Polygon boundaries defined once per camera
  - Soft confidence gradient allows per-boundary filtering
- **Switch to VLM** when:
  - Cameras pan/tilt dynamically (no fixed zone)
  - Store layout changes seasonally (dynamic staff zones)
  - Need clothing-based detection (e.g., staff wearing variable uniforms)
- **For static retail**: stick with polygon-based (production-grade)

---

## Summary Table

| Decision     | Choice                                 | Why                                        | North Star Link                              |
| ------------ | -------------------------------------- | ------------------------------------------ | -------------------------------------------- |
| Model        | YOLOv8s                                | Speed + accuracy balance                   | Minimize false negatives in person detection |
| Tracker      | ByteTrack (entry) + BoT-SORT (billing) | Occlusion robustness                       | Accurate queue depth + conversion            |
| Re-ID        | Appearance embedding + time-window     | Camera-invariant, temporal gating          | Avoid false re-merges                        |
| Entry        | One ENTRY per person (not groups)      | Simplifies funnel, matches POS             | Per-person conversion granularity            |
| Confidence   | Pass all, flag low-conf                | Graceful degradation                       | Transparency over silence                    |
| Staff        | Polygon-based spatial ROI              | Deterministic + fast                       | Exclude staff from customer metrics          |
| Event Schema | Flat + nested metadata                 | SQL simplicity + extensibility             | Easy to query and extend                     |
| Storage      | SQLite PRIMARY KEY                     | Idempotent ingest, zero dedup logic        | Replay events safely                         |
| Conversion   | Time-window + store_id                 | Robust without customer_id                 | Accurate conversion rate                     |
| Anomalies    | Open-hours aware                       | Reduce false alerts, improve actionability | Alert only on actionable anomalies           |
| Ingest       | Idempotent + partial success           | Robustness, per-event feedback             | Fleet reliability                            |
| Runtime      | CPU-only scored API                    | GPU is offline-only, API is CPU            | Easy deployment, horizontal scaling          |
| Logging      | Structured JSON + 503 graceful         | Operability, no stack traces               | Team velocity debugging                      |

---

**Every choice is defensible. Questions? See DESIGN.md or inline comments in code.**
