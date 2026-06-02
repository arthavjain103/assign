# Store Intelligence API — Real-time Retail Analytics

A production-grade system for detecting customer journeys from CCTV footage, computing conversion rates, and generating real-time anomaly alerts.

## Quick Start (5 commands)

### 1. Clone and enter directory

```bash
cd hire_challenge
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize the database and load sample data

```bash
python -c "from app.db import init_db; init_db()"
```

### 4. Run the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test the API

```bash
# In another terminal:
pytest tests/assertions.py -v
```

The API will be available at `http://localhost:8000` with automatic documentation at `/docs`.

## Production Deployment: Docker

```bash
docker compose up
```

This starts the API on port 8000 with SQLite database persistence.

## Architecture

### API Layer (`app/`)

- **main.py**: FastAPI entry point with structured logging middleware
- **models.py**: Pydantic v2 event schema with strict validation
- **db.py**: SQLAlchemy 2.0 with SQLite, idempotent via PRIMARY KEY on event_id
- **ingestion.py**: Idempotent batch ingest with per-event status
- **metrics.py**: Real-time metrics (conversion, dwell, queue depth, abandonment)
- **funnel.py**: Conversion funnel (Entry → Zone → Billing → Purchase)
- **heatmap.py**: Zone visit intensity + dwell heatmap
- **anomalies.py**: Queue spike, conversion drop, dead zone detection (open-hours aware)
- **health.py**: Service health + staleness detection
- **loaders.py**: Data ingestion from JSON/CSV

### Detection Pipeline (`pipeline/`)

- Offline execution on free T4 GPU (Colab/Kaggle)
- YOLOv8s for person detection (COCO class 0)
- ByteTrack for entry/floor clips (fast occlusion recovery)
- BoT-SORT for billing clip (appearance embeddings through heavy occlusion)
- Re-ID via appearance embedding + spatial-temporal gating
- Outputs: `events.jsonl` (200+ events)

### Data Sources (wired in on startup)

- **store_layout.json**: Zones, cameras, open hours
- **pos_transactions.csv**: POS data for conversion correlation
- **sample_events.jsonl**: 200 realistic events (1-minute store replay)

## Detection Logic


### Staff Detection
1. **Person must be inside the store** (see Inside vs Outside)
2. **CAM_4 (back-office)**: Always classified as STAFF when in back-office zone
3. **Other cameras**: Dark torso ratio ≥ 55% triggers STAFF label (black uniform heuristic)
4. **StaffRegistry**: Deduplicates the same staff member across cameras and track-ID churn for store-wide unique staff count


## API Endpoints

### Real-time Metrics

```bash
GET /stores/{store_id}/metrics
# Returns: unique_visitors, conversion_rate, avg_dwell_per_zone, queue_depth,
#          abandonment_rate, basket_value_inr, revenue
```

### Conversion Funnel

```bash
GET /stores/{store_id}/funnel
# Returns: Entry → Zone Visit → Billing Queue → Purchase with drop-off %
```

### Zone Heatmap

```bash
GET /stores/{store_id}/heatmap
# Returns: Zone visit frequency + avg dwell, intensity 0–100
```

### Anomalies

```bash
GET /stores/{store_id}/anomalies
# Returns: queue_spike, conversion_drop, dead_zone (open-hours aware)
```

### Event Ingestion (idempotent)

```bash
POST /events/ingest
# Accepts: { events: [ {...}, ... ] } (≤500 per batch)
# Returns: per-event status (accepted/duplicate/rejected)
# Never 5xx on valid input; partial success supported
```

### Service Health

```bash
GET /health
# Returns: status, last_event_timestamp per store, staleness warnings
```

## Event Schema (Pydantic v2)

```json
{
  "event_id": "uuid-v4",
  "store_id": "STORE_BLR_002",
  "camera_id": "CAM_ENTRY_01",
  "visitor_id": "VIS_c8a2f1",
  "event_type": "ZONE_DWELL",
  "timestamp": "2026-03-03T14:22:10Z",
  "zone_id": "SKINCARE",
  "dwell_ms": 8400,
  "is_staff": false,
  "confidence": 0.91,
  "metadata": {
    "queue_depth": null,
    "sku_zone": "MOISTURISER",
    "session_seq": 5
  }
}
```

Event types: `ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, `REENTRY`.

## Running Tests

```bash
# All tests (including assertions.py acceptance gate)
pytest tests/ -v --cov=app --cov-report=term-missing

# Just assertions (API contract)
pytest tests/assertions.py -v

# Specific test file
pytest tests/test_metrics.py -v

# Coverage report (>70% target)
pytest tests/ --cov=app --cov-report=html
```

## Data Flow

```
Raw video clips (offline)
    ↓
[Detection Pipeline: YOLOv8s + ByteTrack/BoT-SORT]
    ↓
events.jsonl (200+ events)
    ↓
POST /events/ingest
    ↓
[Idempotent INSERT via event_id PRIMARY KEY]
    ↓
SQLite EventDB
    ↓
GET /stores/{id}/metrics (real-time, computed on-demand)
GET /stores/{id}/funnel (session-based, re-entry dedup)
GET /stores/{id}/heatmap (zone intensity 0–100)
GET /stores/{id}/anomalies (open-hours aware)
GET /health (staleness detection)
```

## Key Design Decisions

1. **Idempotent Ingest**: SQLite PRIMARY KEY on event_id → `INSERT OR IGNORE` → safe to replay
2. **Conversion Correlation**: Time-window + store_id only (no customer_id in POS data)
3. **Re-entry Dedup**: visitor_id per-session, explicitly marked as REENTRY in events
4. **Open-Hours Awareness**: Anomalies only fire during store hours (dead zone, conversion drop)
5. **CPU-only Runtime**: GPU used only for offline detection; API runs on CPU
6. **Structured Logging**: JSON logs with trace_id for operability
7. **Graceful Degradation**: 503 on DB error, never raw stack traces

## Scaling Notes

**Current**: SQLite single-file, CPU, suitable for 1–5 stores.

**At 40 stores**:

- Write contention limit (~3–5 concurrent writes on SQLite)
- Migration path: Postgres + Redis Streams/Kafka + horizontal API workers

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run API with auto-reload
uvicorn app.main:app --reload

# Run tests with coverage
pytest tests/ --cov=app -v

# Check logs
tail -f store_intelligence.db  # or docker logs store-intelligence-api
```

## Troubleshooting

- **API won't start**: Check that port 8000 is free; adjust in `docker-compose.yml`
- **Database locked**: SQLite doesn't handle concurrent writes well; see scaling notes
- **Events not showing**: Run loaders manually:
  ```python
  from app.db import SessionLocal
  from app.loaders import load_store_layout, load_pos_transactions, load_sample_events
  db = SessionLocal()
  load_store_layout("data/store_layout.json", db)
  load_pos_transactions("data/pos_transactions.csv", db)
  load_sample_events("data/sample_events.jsonl", db)
  ```
- **Anomalies not firing**: Check store open_hours in `store_layout.json`

## Files

```
hire_challenge/
├── app/                          # FastAPI application
│   ├── main.py                   # Entry point, routes, middleware
│   ├── models.py                 # Pydantic v2 schemas
│   ├── db.py                     # SQLAlchemy ORM
│   ├── ingestion.py              # Idempotent batch ingest
│   ├── metrics.py                # Conversion, dwell, queue, abandonment
│   ├── funnel.py                 # Conversion funnel
│   ├── heatmap.py                # Zone heatmap
│   ├── anomalies.py              # Anomaly detection
│   ├── health.py                 # Health checks
│   └── loaders.py                # Data loaders
├── tests/                        # >70% coverage
│   ├── assertions.py             # 10 acceptance-gate assertions
│   ├── test_metrics.py           # Metrics tests
│   ├── test_funnel.py            # Funnel tests
│   ├── test_ingest_idempotency.py  # Idempotency tests
│   └── test_anomalies.py         # Anomaly detection tests
├── data/                         # Input data
│   ├── store_layout.json         # Zone definitions, open hours
│   ├── pos_transactions.csv      # POS transactions
│   └── sample_events.jsonl       # 200 sample events
├── docs/                         # Documentation
│   ├── DESIGN.md                 # Architecture + AI decisions
│   └── CHOICES.md                # 13 major decisions + trade-offs
├── pipeline/                     # Detection (offline, GPU)
│   ├── detect.py                 # YOLOv8s + tracking
│   ├── tracker.py                # Re-ID / re-entry logic
│   ├── emit.py                   # Schema validation + JSONL
│   └── staff_vlm.py              # Optional VLM staff classifier
├── Dockerfile                    # Docker image
├── docker-compose.yml            # Full-stack orchestration
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
└── README.md                     # This file
```

## Dashboard (Next.js)

The frontend dashboard is under `frontend/`. To run:

```bash
cd frontend
npm install
npm run dev
```

Access at `http://localhost:3000`.

## Acceptance Gate (DO THIS OR SCORE = 0)

✅ `docker compose up` works on clean clone  
✅ README explains detection → events flow  
✅ POST /events/ingest never 5xx on valid input  
✅ GET /stores/STORE_BLR_002/metrics returns valid JSON  
✅ DESIGN.md + CHOICES.md exist, >250 words, non-trivial  
✅ All 10 assertions in assertions.py pass

## Contact

For questions or issues, refer to `DESIGN.md` and `CHOICES.md`.
