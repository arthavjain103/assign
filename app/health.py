"""
Health check: service status, last event per store, staleness detection.
"""
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from .models import HealthResponse
from .db import EventDB

logger = logging.getLogger(__name__)

STALE_THRESHOLD_MINUTES = 10


def compute_health(db: Session) -> HealthResponse:
    """
    Compute service health: status, last event timestamp per store, staleness warnings.
    """
    try:
        now = datetime.utcnow()
        stores_data = {}

        # Get all stores in the database
        stores = db.query(EventDB.store_id).distinct().all()

        for (store_id,) in stores:
            # Last event timestamp
            last_event = db.query(func.max(EventDB.timestamp)).filter(
                EventDB.store_id == store_id
            ).scalar()

            if last_event:
                lag_ms = int((now - last_event).total_seconds() * 1000)
                is_stale = lag_ms > STALE_THRESHOLD_MINUTES * 60 * 1000

                stores_data[store_id] = {
                    "last_event_timestamp": last_event.isoformat() + "Z",
                    "lag_ms": lag_ms,
                    "stale": is_stale,
                }
            else:
                stores_data[store_id] = {
                    "last_event_timestamp": None,
                    "lag_ms": None,
                    "stale": True,
                }

        # Determine overall status
        stale_stores = sum(1 for s in stores_data.values() if s.get("stale"))
        status = "healthy" if stale_stores == 0 else (
            "degraded" if stale_stores < len(stores_data) else "unhealthy"
        )

        return HealthResponse(
            status=status,
            timestamp=now.isoformat() + "Z",
            stores=stores_data,
        )

    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow().isoformat() + "Z",
            stores={},
        )
