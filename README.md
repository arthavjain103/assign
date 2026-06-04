# Store Intelligence API — Real-time Retail Analytics Platform

> Real-time detection, tracking, and analytics for retail store operations. Transforms video into actionable business intelligence.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Setup & Installation](#setup--installation)
5. [Detection Pipeline](#detection-pipeline)
6. [Staff Detection Logic](#staff-detection-logic)
7. [API Reference](#api-reference)
8. [Data Flow](#data-flow)
9. [Design Decisions](#design-decisions)
10. [Dashboard](#dashboard)
11. [Development](#development)
12. [Troubleshooting](#troubleshooting)

---

## Overview

Store Intelligence is a comprehensive retail analytics platform that:

- Detects and tracks people across multiple video feeds using YOLOv8s + Ultralytics tracking
- Identifies staff automatically (black & pink uniform detection)
- Computes metrics in real-time: queue depth, conversion rates, dwell time, anomalies
- Scales intelligently: SQLite for 1–5 stores, Postgres for enterprise
- Ensures consistency: Idempotent event ingestion with MD5 deduplication
- Visualizes data: Next.js dashboard with live metrics and heatmaps

### Key Features

| Feature                   | Details                                                               |
| ------------------------- | --------------------------------------------------------------------- |
| **Person Detection**      | YOLOv8s (640×640, half-precision FP16)                                |
| **Multi-Camera Tracking** | ByteTrack (entry/floor), BoT-SORT (billing queue)                     |
| **Staff Identification**  | Dark (≥55%) & pink (≥50%) uniform detection + cross-camera dedup      |
| **Event Types**           | ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, BILLING_QUEUE_JOIN, REENTRY, etc. |
| **Queue Analytics**       | Automatic customer-only queue depth (staff filtered out)              |
| **Conversion Tracking**   | Links billing zone visits to POS transactions (5-min window)          |
| **Anomaly Detection**     | Flags unusual patterns: abandoned carts, crowd surge, etc.            |

---

## Quick Start

### 5-Minute Setup (Development)

```bash
git clone <repo-url>
cd hire_challenge

pip install -r requirements.txt

python -c "from app.db import init_db; init_db()"
python -c "from app.loaders import load_store_layout, load_pos_transactions; load_store_layout('STORE_BLR_001'); load_pos_transactions('STORE_BLR_001')"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pytest tests/assertions.py -v
```

### Production Deployment (Docker)

```bash
docker compose up
```

Starts:

- FastAPI backend on port 8000
- Next.js dashboard on port 3000
- SQLite database (auto-initialized)

---

## Architecture

### System Components

```
PostgreSQL Layer: FastAPI (Python)
├─ Frontend: Next.js Dashboard (React + TypeScript)
│  ├─ Real-time metrics & KPIs
│  ├─ Queue depth visualization & heatmaps
│  └─ Anomaly alerts & conversion funnel
├─ API Layer: FastAPI (Python)
│  ├─ GET /stores/{store_id}/metrics
│  ├─ GET /stores/{store_id}/funnel
│  ├─ GET /stores/{store_id}/heatmap
│  ├─ POST /events/ingest (idempotent)
│  └─ GET /stores/{store_id}/anomalies
├─ Detection Pipeline: Offline GPU Processing
│  ├─ YOLOv8s person detection
│  ├─ ByteTrack/BoT-SORT multi-object tracking
│  ├─ Staff classification (uniform colors)
│  └─ Cross-camera re-ID (appearance embeddings)
└─ Data Layer: SQLite (+ Postgres for scale)
   ├─ EventDB: normalized event log
   ├─ SessionDB: visitor sessions & dwell times
   └─ POSTransactionDB: retail sales data
```

### Technology Stack

- Backend: FastAPI, SQLAlchemy 2.0, Pydantic v2
- Detection: Ultralytics YOLOv8s, PyTorch
- Tracking: Native Ultralytics ByteTrack / BoT-SORT
- Frontend: Next.js, React, TypeScript, Vite
- Database: SQLite (dev), Postgres (production)
- Logging: Structlog (JSON structured logs)
- Container: Docker + Docker Compose

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- Docker & Docker Compose (for production)
- CUDA 11.8+ (optional, for GPU acceleration)

### Development Setup

```bash
git clone <url>
cd hire_challenge

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

python << 'EOF'
from app.db import init_db
init_db()
print("Database initialized")
EOF

python << 'EOF'
from app.loaders import load_store_layout, load_pos_transactions, load_sample_events
load_store_layout("STORE_BLR_001")
load_pos_transactions("STORE_BLR_001")
load_sample_events("STORE_BLR_001")
print("Sample data loaded")
EOF

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000/docs for interactive API docs (Swagger UI).

### Frontend Setup

```bash
cd frontend
npm install

npm run dev

npm run build
npm run preview
```

---

## Detection Pipeline

### Overview

Raw video files are processed offline through a GPU pipeline that:

1. Detects all persons using YOLOv8s (person class only, conf=0.25)
2. Tracks them across frames with motion + appearance features
3. Classifies staff based on uniform colors
4. Re-identifies visitors across cameras (cross-clip dedup)
5. Emits events as structured JSON (events.jsonl)

### Processing Flow

```
Video File (mp4/avi)
    [YOLOv8s Detection]
    ├─ Confidence >= 0.25 (keep all detections with metadata)
    ├─ FP16 (half-precision) for speed
    └─ Person class only (COCO class 0)
    [Ultralytics Native Tracking]
    ├─ Entry/Floor: ByteTrack (motion-based, fast)
    ├─ Billing: BoT-SORT (appearance embeddings, dense queues)
    └─ Persistence across frame drops
    [Staff Classification]
    ├─ Entry line check (inside/outside store)
    ├─ Dark torso ratio >=55% -> BLACK uniform staff
    ├─ Pink torso ratio >=50% -> PINK uniform staff
    └─ Back-office zone -> Automatic staff
    [Cross-Camera Re-ID]
    ├─ Compare appearance embeddings
    ├─ Match if similarity > 0.7 AND time delta < 15 min
    └─ Link reentries across clips
    [Event Emission]
    └─ events.jsonl (newline-delimited JSON)
        ├─ ENTRY/EXIT (vertical line crossing)
        ├─ ZONE_ENTER/ZONE_EXIT (zone boundary crossing)
        ├─ ZONE_DWELL (30-second boundary ticks)
        ├─ BILLING_QUEUE_JOIN (customer in queue)
        └─ REENTRY (revisiting customer)
```

### Camera Configuration

| Camera  | Type         | Clip Type   | Tracker   | Purpose                  |
| ------- | ------------ | ----------- | --------- | ------------------------ |
| CAM_1/2 | Floor view   | floor       | ByteTrack | General store navigation |
| CAM_3   | Entry gate   | entry       | ByteTrack | Entry/exit counting      |
| CAM_4   | Back-office  | back_office | ByteTrack | Staff tracking           |
| CAM_5   | Billing zone | billing     | BoT-SORT  | Queue depth, conversions |

---

## Staff Detection Logic

### Multi-Step Classification

Staff detection uses three independent signals to classify employees:

#### 1. Entry Line Check (CAM_3 Only)

- Line position: y = 0.55 \* frame_height
- Above line: OUTSIDE store (ignore)
- Below line: INSIDE store (process)

#### 2. Back-Office Zone (CAM_4 Only)

- Polygon defined by 4 points (top-left, top-right, bottom-right, bottom-left)
- Inside polygon: Automatic STAFF classification (confidence: 0.95)
- Outside polygon: Check uniform color

#### 3. Uniform Color Detection (All Cameras)

Black Uniform Detection:

```python
dark_mask = (saturation < 100) AND (value < 100)
dark_ratio = count(dark_pixels) / total_pixels
if dark_ratio >= 0.55 -> STAFF
```

Pink Uniform Detection:

```python
pink_mask = ((hue <= 25) OR (hue >= 150))
        AND (saturation > 100)
        AND (value > 50)
if pink_ratio >= 0.50 -> STAFF
```

### Cross-Camera Staff Deduplication

Each staff member detected across cameras is assigned a unique STAFF_ID:

- Matches via body signature (HSV histogram, cosine similarity >= 0.72)
- Persists across track ID churn
- Tracked in StaffRegistry with:
  - Body signature (HSV histogram)
  - Last seen timestamp
  - Cameras visited

### Queue Depth Calculation (Billing Zone)

```python
queue_depth = count(distinct customers in billing zone) - staff_count
```

Formula logic:

- Count all people detected in billing zone
- Subtract staff (black OR pink uniform detection)
- Result = pure customer queue depth

Why this matters:

- Staff moving through queue artificially inflates wait times
- Filtering ensures accurate conversion metrics
- Pink + black uniform coverage handles diverse staff dress codes

---

## API Reference

### Base URL

```
http://localhost:8000
```

### Authentication

None (development). Add OAuth2 for production.

### Endpoints

#### 1. GET /stores/{store_id}/metrics

Real-time KPIs for a store.

```bash
curl http://localhost:8000/stores/STORE_BLR_001/metrics
```

Response:

```json
{
  "store_id": "STORE_BLR_001",
  "timestamp": "2026-06-04T10:30:00Z",
  "unique_visitors": 42,
  "current_queue_depth": 5,
  "conversion_rate": 0.238,
  "avg_dwell_sec": 285,
  "zone_counts": {
    "ENTRY": 42,
    "FLOOR": 38,
    "BILLING": 23
  }
}
```

#### 2. GET /stores/{store_id}/funnel

Conversion funnel: Entry -> Floor -> Billing -> POS Transaction.

```bash
curl http://localhost:8000/stores/STORE_BLR_001/funnel
```

Response:

```json
{
  "store_id": "STORE_BLR_001",
  "funnel": [
    { "stage": "entry", "count": 42, "percentage": 100.0 },
    { "stage": "floor", "count": 38, "percentage": 90.5 },
    { "stage": "billing", "count": 23, "percentage": 54.8 },
    { "stage": "converted", "count": 10, "percentage": 23.8 }
  ],
  "abandonment": {
    "floor_to_billing": 8,
    "billing_to_pos": 13
  }
}
```

#### 3. GET /stores/{store_id}/heatmap

Zone-by-zone traffic distribution.

```bash
curl http://localhost:8000/stores/STORE_BLR_001/heatmap
```

#### 4. POST /events/ingest (Idempotent)

Batch ingest detection events (events.jsonl).

```bash
curl -X POST http://localhost:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": "STORE_BLR_001",
    "events": [
      {
        "event_id": "ev_abc123",
        "visitor_id": "VIS_001",
        "event_type": "ZONE_ENTER",
        "zone_id": "FLOOR",
        "timestamp": "2026-06-04T10:00:00Z",
        "dwell_ms": 0,
        "is_staff": false,
        "confidence": 0.92
      }
    ]
  }'
```

Key feature: Duplicate events (same event_id) are silently ignored. Safe to retry.

#### 5. GET /stores/{store_id}/anomalies

Flag unusual patterns.

```bash
curl http://localhost:8000/stores/STORE_BLR_001/anomalies
```

#### 6. GET /health

Service health check.

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "ok",
  "database": "connected",
  "uptime_sec": 3600
}
```

---

## Data Flow

### End-to-End Pipeline

```
Video Files (mp4)
  [Detection Pipeline - Offline GPU]
  ├─ YOLOv8s detection (person only)
  ├─ ByteTrack/BoT-SORT tracking
  ├─ Staff classification (uniform colors)
  └─ Cross-camera re-ID
  [events.jsonl] (streaming output)
     [API Ingestion - POST /events/ingest]
     ├─ Pydantic schema validation
     ├─ MD5 deduplication (idempotent)
     └─ SQLite insert
  [SQLite Database]
     ├─ EventDB table (all events)
     ├─ SessionDB table (visitor sessions)
     └─ POSTransactionDB table (sales data)
  [Metrics Computation - On-Demand]
     ├─ Query visitors + zones + dwell times
     ├─ Filter staff out of queue calculations
     ├─ Link conversions (billing zone + POS within 5 min)
     └─ Compute: queue_depth, conversion_rate, anomalies
  [Next.js Dashboard]
     ├─ Fetch /stores/{id}/metrics
     ├─ Render: KPIs, heatmaps, funnel, alerts
     └─ Real-time updates every 5 sec
```

---

## Design Decisions

### 1. Idempotent Event Ingestion

- Events are uniquely identified by event_id (MD5 hash)
- Duplicate ingestions are safely ignored
- Allows reliable batch processing with retry semantics

### 2. Time-Window Conversion Correlation

- Visitor in billing zone within 5 minutes before POS transaction = converted
- Accounts for card processing delay
- More accurate than simple zone-to-transaction matching

### 3. Staff Filtering in Queue Depth

- Queue metrics exclude staff (both black & pink uniforms)
- Prevents inflated wait time estimates
- Improves customer experience metrics accuracy

### 4. Multi-Tracker Strategy

- ByteTrack (entry/floor): Fast, motion-only, handles rapid movement
- BoT-SORT (billing): Appearance-based, excels in dense stationary queues

### 5. Open-Hours Awareness

- Separate analytics for business hours vs. off-hours
- Configurable per store

### 6. CPU-Only Runtime (GPU for Pipeline)

- API server runs on CPU (FastAPI)
- Video processing offloaded to GPU (ultralytics)
- Decouples inference from serving

### 7. Structured JSON Logging

- Every request/response logged with:
  - Unique trace_id (UUID)
  - Request path & status code
  - Latency in ms
- Enables debugging & performance analysis

---

## Dashboard

### Frontend Setup

```bash
cd frontend/store-intelligence
pnpm install
pnpm dev
```

Access at http://localhost:3000.

### Features

| Component           | Purpose                                                   |
| ------------------- | --------------------------------------------------------- |
| **KPI Command Bar** | Real-time metrics: queue depth, conversion rate, visitors |
| **Camera Wall**     | Live/recorded stream from all cameras                     |
| **Queue Gauge**     | Current billing queue depth (animated)                    |
| **Heatmap**         | Zone traffic density visualization                        |
| **Funnel Chart**    | Entry -> Floor -> Billing -> Conversion stages            |
| **Session Table**   | Individual visitor timelines & dwell times                |
| **Anomaly Panel**   | Alerts: queue surge, abandoned cart, etc.                 |
| **Event Stream**    | Live event feed (filtered by type)                        |

### Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- pnpm (package manager)

---

## Development

### Running Tests

```bash
pytest tests/assertions.py -v

pytest tests/ -v --cov=app --cov-report=html

pytest tests/test_metrics.py -v

pytest tests/test_metrics.py::test_metrics_funnel -v
```

### Test Coverage

- Idempotent event ingestion
- Metrics calculation (queue depth, conversion rate)
- Funnel stage counting
- Heatmap zone aggregation
- Anomaly detection logic
- Session dwell time tracking
- Cross-camera re-ID edge cases
- Staff filtering in queue depth
- Open-hours filters
- POS conversion correlation

### Code Structure

```
app/
├── main.py
├── db.py
├── models.py
├── ingestion.py
├── metrics.py
├── funnel.py
├── heatmap.py
├── anomalies.py
├── health.py
└── loaders.py

pipeline/
├── detect.py
├── staff_vlm.py
├── tracker.py
├── emit.py
└── run_pipeline.py

tests/
├── assertions.py
├── test_*.py
└── conftest.py
```

### Debugging Tips

1. Check structured logs (JSON format):

```bash
tail -f app.log | jq .
```

2. Enable verbose detection output:

```python
logger.setLevel(logging.DEBUG)
```

3. Inspect event schema validation:

```bash
curl -X POST http://localhost:8000/events/ingest \
  -d '{"invalid": "data"}' 2>&1 | jq .detail
```

4. Profile metrics query:

```python
import time
start = time.time()
metrics = compute_metrics(db, "STORE_BLR_001")
print(f"Query took {(time.time() - start) * 1000:.1f}ms")
```

---

## Troubleshooting

### API Won't Start

```
Error: Address already in use (:8000)
```

Solution:

```bash
lsof -i :8000
kill -9 <PID>
```

Or use different port:

```bash
uvicorn app.main:app --port 8001
```

### Database Locked

```
Error: database is locked
```

Solution:

```bash
rm app.db-wal app.db-shm

python -c "from app.db import init_db; init_db()"
```

### Events Not Appearing

1. Check ingestion log: `tail -f app.log | jq '.event_type'`
2. Verify event_id uniqueness: Duplicates are silently ignored
3. Check timestamp format: Must be ISO 8601 (`2026-06-04T10:00:00Z`)

### Queue Depth Incorrect

- Verify staff detection: Are pink/black uniforms detected?

```bash
curl http://localhost:8000/stores/STORE_ID/metrics | jq .zone_counts
```

- Check billing zone boundary: Defined in `pipeline/staff_vlm.py` -> `STAFF_ZONE_POLYGON`

### Slow Metrics Query

- Add database index on timestamp:

```sql
CREATE INDEX idx_events_timestamp ON event (timestamp DESC);
```

- Limit query window (e.g., last 24 hours instead of all-time)

---

## Files & Directories

```
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── db.py
│   ├── models.py
│   ├── ingestion.py
│   ├── metrics.py
│   ├── funnel.py
│   ├── heatmap.py
│   ├── anomalies.py
│   ├── health.py
│   └── loaders.py
├── pipeline/
│   ├── detect.py
│   ├── staff_vlm.py
│   ├── tracker.py
│   ├── emit.py
│   └── run_pipeline.py
├── frontend/
│   └── store-intelligence/
│       ├── src/
│       │   ├── App.tsx
│       │   ├── components/
│       │   ├── hooks/
│       │   └── lib/
│       ├── package.json
│       └── vite.config.ts
├── tests/
│   ├── assertions.py
│   ├── test_api_integrity.py
│   ├── test_metrics.py
│   ├── test_funnel.py
│   ├── test_ingest_idempotency.py
│   └── conftest.py
├── data/
│   └── sample_events.jsonl
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── README.md
├── DESIGN.md
└── CHOICES.md
```

---

For detailed architecture & decision rationale, see DESIGN.md and CHOICES.md.
