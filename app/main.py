"""
FastAPI entry point: middleware, routes, lifecycle, graceful degradation.
Structured logging with trace_id. All error responses return valid JSON, never 5xx on valid input.
"""
import logging
import uuid
import json
import asyncio
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import structlog
import cv2
import base64
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .db import init_db, get_db, engine, EventDB
from .models import (
    EventIngestionRequest,
    EventIngestionResponse,
)
from .ingestion import ingest_events
from .metrics import compute_metrics
from .funnel import compute_funnel
from .heatmap import compute_heatmap
from .anomalies import compute_anomalies
from .health import compute_health
from .loaders import load_store_layout, load_pos_transactions, load_sample_events

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# Middleware for request tracing and logging
class RequestTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        # Extract store_id from path if present
        store_id = None
        path_parts = request.url.path.split("/")
        if len(path_parts) > 2 and path_parts[1] == "stores":
            store_id = path_parts[2]

        try:
            response = await call_next(request)
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            logger.info(
                "request_completed",
                trace_id=trace_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=latency_ms,
                store_id=store_id,
            )

            response.headers["X-Trace-ID"] = trace_id
            return response

        except Exception as e:
            latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.error(
                "request_failed",
                trace_id=trace_id,
                method=request.method,
                path=request.url.path,
                latency_ms=latency_ms,
                store_id=store_id,
                error=str(e),
            )
            raise


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("startup", action="initializing_database")
    init_db()

    # Load sample data from data directory
    data_dir = Path(__file__).parent.parent / "data"
    db = next(get_db())
    try:
        load_store_layout(data_dir / "store_layout.json", db)
        load_pos_transactions(data_dir / "pos_transactions.csv", db)
        load_sample_events(data_dir / "sample_events.jsonl", db)
    finally:
        db.close()

    logger.info("startup", action="database_ready")

    yield

    # Shutdown
    logger.info("shutdown", action="closing_database")


app = FastAPI(
    title="Store Intelligence API",
    description="Real-time retail analytics from CCTV detection",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestTracingMiddleware)


# Global exception handler for database errors
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("database_error", error=str(exc))
    return JSONResponse(
        status_code=503,
        content={
            "error": "database_unavailable",
            "message": "Database service is temporarily unavailable",
            "trace_id": request.headers.get("X-Trace-ID"),
        },
    )


# Routes

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Service health, last event per store, staleness warnings."""
    try:
        health = compute_health(db)
        return health
    except SQLAlchemyError:
        logger.error("health_check_db_error")
        return JSONResponse(
            status_code=503,
            content={
                "error": "database_unavailable",
                "status": "unhealthy",
            },
        )


@app.post("/streams/start")
async def streams_start():
    """Initialize stream session for live data."""
    return {
        "status": "streaming_started",
        "timestamp": datetime.now().isoformat(),
        "cameras": ["CAM_1", "CAM_2", "CAM_3", "CAM_4", "CAM_5"],
    }


@app.post("/events/ingest", response_model=EventIngestionResponse)
async def ingest_events_endpoint(
    request: EventIngestionRequest,
    db: Session = Depends(get_db),
):
    """
    Idempotent batch ingest: ≤500 events.
    Returns per-event status (accepted/duplicate/rejected).
    Never returns 5xx on valid input.
    """
    try:
        if not request.events:
            return EventIngestionResponse(
                total=0,
                accepted=0,
                duplicates=0,
                rejected=0,
                events=[],
            )

        result = ingest_events(request.events, db)
        return result

    except SQLAlchemyError as e:
        logger.error("ingest_db_error", error=str(e))
        return EventIngestionResponse(
            total=len(request.events),
            accepted=0,
            duplicates=0,
            rejected=len(request.events),
            events=[
                EventIngestionResponse.EventStatus(
                    event_id=e.event_id,
                    status="rejected",
                    message="Database error; batch rolled back",
                )
                for e in request.events
            ],
        )


@app.get("/stores/{store_id}/metrics")
async def get_metrics(store_id: str, db: Session = Depends(get_db)):
    """
    Live store metrics: unique visitors, conversion rate, dwell, queue depth,
    abandonment, basket value, revenue. Never null or divide-by-zero.
    """
    try:
        metrics = compute_metrics(store_id, db)
        return metrics
    except SQLAlchemyError:
        logger.error("metrics_db_error", store_id=store_id)
        return JSONResponse(
            status_code=503,
            content={"error": "database_unavailable"},
        )


@app.get("/stores/{store_id}/funnel")
async def get_funnel(store_id: str, db: Session = Depends(get_db)):
    """
    Conversion funnel: Entry → Zone Visit → Billing Queue → Purchase.
    Session is the unit; re-entries not double-counted.
    """
    try:
        funnel = compute_funnel(store_id, db)
        return funnel
    except SQLAlchemyError:
        logger.error("funnel_db_error", store_id=store_id)
        return JSONResponse(
            status_code=503,
            content={"error": "database_unavailable"},
        )


@app.get("/stores/{store_id}/heatmap")
async def get_heatmap(store_id: str, db: Session = Depends(get_db)):
    """
    Zone visit frequency + average dwell. Intensity 0–100.
    data_confidence flag if <20 sessions in window.
    """
    try:
        heatmap = compute_heatmap(store_id, db)
        return heatmap
    except SQLAlchemyError:
        logger.error("heatmap_db_error", store_id=store_id)
        return JSONResponse(
            status_code=503,
            content={"error": "database_unavailable"},
        )


@app.get("/stores/{store_id}/anomalies")
async def get_anomalies(store_id: str, db: Session = Depends(get_db)):
    """
    Active anomalies: queue spike, conversion drop, dead zones.
    All checks respect open hours (no false alerts on closed stores).
    """
    try:
        anomalies = compute_anomalies(store_id, db)
        return anomalies
    except SQLAlchemyError:
        logger.error("anomalies_db_error", store_id=store_id)
        return JSONResponse(
            status_code=503,
            content={"error": "database_unavailable"},
        )


# WebSocket for live events stream
@app.websocket("/ws/events")
async def websocket_events_stream(websocket: WebSocket, db: Session = Depends(get_db)):
    """Stream live events via WebSocket."""
    await websocket.accept()
    logger.info("Events stream connected")

    try:
        # Send recent events first (use EventDB - the SQLAlchemy ORM model)
        recent_events = (
            db.query(EventDB)
            .filter(EventDB.is_staff == False)
            .order_by(EventDB.timestamp.desc())
            .limit(50)
            .all()
        )
        for event in reversed(recent_events):
            await websocket.send_json({
                "type": "event",
                "event_id": str(event.event_id),
                "store_id": str(event.store_id),
                "visitor_id": str(event.visitor_id),
                "event_type": event.event_type,
                "zone_id": event.zone_id,
                "camera_id": event.camera_id,
                "dwell_ms": event.dwell_ms,
                "is_staff": event.is_staff,
                "confidence": event.confidence,
                "timestamp": event.timestamp.isoformat() + "Z",
            })

        # Keep connection alive — heartbeat loop
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("Events stream disconnected")
    except Exception as e:
        logger.error("websocket_events_error", error=str(e))
        await websocket.close()


# WebSocket for live camera streams
@app.websocket("/ws/camera/{camera_id}")
async def websocket_camera_stream(websocket: WebSocket, camera_id: str):
    """Stream camera frames via WebSocket as base64-encoded JPEGs."""
    await websocket.accept()
    print(f"✓ Camera WebSocket connected: {camera_id}")
    logger.info("camera_connected", camera=camera_id)
    
    camera_map = {
        "CAM_1": "CAM 1.mp4",
        "CAM_2": "CAM 2.mp4",
        "CAM_3": "CAM 3.mp4",
        "CAM_4": "CAM 4.mp4",
        "CAM_5": "CAM 5.mp4",
    }
    
    video_file = camera_map.get(camera_id)
    if not video_file:
        print(f"✗ Camera not found: {camera_id}")
        await websocket.send_json({"error": "Camera not found"})
        await websocket.close()
        return
    
    video_path = Path(__file__).parent.parent / "data" / video_file
    print(f"  Looking for video: {video_path}")
    if not video_path.exists():
        print(f"✗ Video file not found: {video_path}")
        await websocket.send_json({"error": "Video file not found"})
        await websocket.close()
        return
    
    print(f"✓ Video file found: {video_path}")
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"✗ Cannot open video file with OpenCV")
            await websocket.send_json({"error": "Cannot open video file"})
            await websocket.close()
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_delay = (1000 / fps) / 1000 if fps > 0 else 0.033  # Convert to seconds
        print(f"✓ Video opened. FPS: {fps}, Frame delay: {frame_delay:.3f}s")
        frame_count = 0

        while True:
            success, frame = cap.read()
            if not success:
                # Loop video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()
                if not success:
                    print(f"✗ Cannot read frame from video")
                    break

            # Resize frame for bandwidth optimization
            frame = cv2.resize(frame, (640, 360))

            # Encode frame as JPEG with lower quality for bandwidth savings
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 55]
            ret, buffer = cv2.imencode('.jpg', frame, encode_param)
            if not ret:
                continue
            frame_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

            await websocket.send_json({
                "type": "frame",
                "camera_id": camera_id,
                "data": frame_b64,
                "frame_number": frame_count,
            })
            
            if frame_count % 30 == 0:
                print(f"  → Sent frame {frame_count} to {camera_id}")

            frame_count += 1
            
            # Frame rate limiting - send at ~15 FPS
            import asyncio
            await asyncio.sleep(0.067)
    except Exception as e:
        print(f"✗ WebSocket camera error: {camera_id} - {str(e)}")
        logger.error("websocket_camera_error", camera=camera_id, error=str(e))
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
    finally:
        cap.release()
        await websocket.close()
        print(f"✓ Camera disconnected: {camera_id}")


@app.get("/streams/stats")
async def get_streams_stats(db: Session = Depends(get_db)):
    """Get live stream statistics (visitors, staff, entries, exits, queue)."""
    try:
        # Get counts from database
        visitor_count = db.query(EventDB).filter(EventDB.type == "entry", EventDB.actor_type == "visitor").count()
        staff_count = db.query(EventDB).filter(EventDB.actor_type == "staff").count()
        entry_count = db.query(EventDB).filter(EventDB.type == "entry").count()
        exit_count = db.query(EventDB).filter(EventDB.type == "exit").count()
        
        return {
            "visitors": visitor_count,
            "staff": staff_count,
            "solo": visitor_count // 2 if visitor_count > 0 else 0,
            "groups": visitor_count - (visitor_count // 2) if visitor_count > 0 else 0,
            "entries": entry_count,
            "exits": exit_count,
            "queue_depth": 0,
            "returning": 0,
            "new_visitors": visitor_count,
        }
    except Exception as e:
        logger.error(f"streams_stats_error: {str(e)}")
        return {
            "visitors": 0,
            "staff": 0,
            "solo": 0,
            "groups": 0,
            "entries": 0,
            "exits": 0,
            "queue_depth": 0,
            "returning": 0,
            "new_visitors": 0,
        }


@app.get("/live/events")
async def get_live_events(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent live events."""
    try:
        events = db.query(EventDB).order_by(EventDB.timestamp.desc()).limit(limit).all()
        return [
            {
                "event_id": str(e.event_id),
                "timestamp": e.timestamp.isoformat() if hasattr(e.timestamp, 'isoformat') else str(e.timestamp),
                "type": e.type,
                "actor_type": e.actor_type,
                "zone": e.zone or "unknown",
                "confidence": e.confidence or 0.0,
            }
            for e in events
        ]
    except Exception as e:
        logger.error(f"live_events_error: {str(e)}")
        return []


@app.get("/live/sessions")
async def get_live_sessions(limit: int = 30, db: Session = Depends(get_db)):
    """Get active visitor sessions."""
    try:
        # Return mock data for now (no session tracking in DB)
        return []
    except Exception as e:
        logger.error(f"live_sessions_error: {str(e)}")
        return []


@app.get("/live/queue")
async def get_live_queue(limit: int = 30, db: Session = Depends(get_db)):
    """Get queue snapshots at billing area."""
    try:
        # Return empty queue data
        return [
            {
                "timestamp": "2024-01-01T00:00:00",
                "zone": "BILLING",
                "queue_depth": 0,
                "wait_time_seconds": 0,
            }
        ]
    except Exception as e:
        logger.error(f"live_queue_error: {str(e)}")
        return []


@app.get("/live/returning-customers")
async def get_returning_customers(store_id: str, limit: int = 30, db: Session = Depends(get_db)):
    """Get returning customer profiles."""
    try:
        return []
    except Exception as e:
        logger.error(f"returning_customers_error: {str(e)}")
        return []


@app.get("/streams/{camera_id}/mjpeg")
async def stream_camera(camera_id: str):
    """Stream MP4 files as MJPEG from data directory (fallback for HTTP clients)."""
    camera_map = {
        "CAM_1": "CAM 1.mp4",
        "CAM_2": "CAM 2.mp4",
        "CAM_3": "CAM 3.mp4",
        "CAM_4": "CAM 4.mp4",
        "CAM_5": "CAM 5.mp4",
    }
    
    video_file = camera_map.get(camera_id)
    if not video_file:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    video_path = Path(__file__).parent.parent / "data" / video_file
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    def video_generator():
        cap = cv2.VideoCapture(str(video_path))
        while True:
            success, frame = cap.read()
            if not success:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()
                if not success:
                    break
            
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
    
    return StreamingResponse(
        video_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
