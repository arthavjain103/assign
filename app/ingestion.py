"""
Idempotent event ingestion with per-event status tracking and graceful partial success.
Validates, deduplicates by event_id, and returns structured status for each event.
"""
from datetime import datetime
from typing import Optional
import json
import logging

from sqlalchemy.orm import Session
from sqlalchemy import insert, select

from .models import Event, EventIngestionResponse
from .db import EventDB

logger = logging.getLogger(__name__)


def ingest_events(
    events: list[Event],
    db: Session,
) -> EventIngestionResponse:
    """
    Idempotent batch ingest: validate, dedup by event_id, insert.
    
    Returns per-event status (accepted/duplicate/rejected) + counts.
    Never raises 5xx on valid input; errors are surfaced per-event.
    """
    statuses = []
    accepted_count = 0
    duplicate_count = 0
    rejected_count = 0

    for event in events:
        try:
            # Check if event_id already exists
            existing = db.query(EventDB).filter(
                EventDB.event_id == event.event_id
            ).first()

            if existing:
                statuses.append(
                    EventIngestionResponse.EventStatus(
                        event_id=event.event_id,
                        status="duplicate",
                        message="Event with this event_id already ingested",
                    )
                )
                duplicate_count += 1
                continue

            # Parse timestamp
            timestamp_dt = datetime.fromisoformat(
                event.timestamp.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            # Insert new event
            db_event = EventDB(
                event_id=event.event_id,
                store_id=event.store_id,
                camera_id=event.camera_id,
                visitor_id=event.visitor_id,
                event_type=event.event_type.value,
                timestamp=timestamp_dt,
                zone_id=event.zone_id,
                dwell_ms=event.dwell_ms,
                is_staff=event.is_staff,
                confidence=event.confidence,
                event_metadata=json.dumps(event.metadata),
            )
            db.add(db_event)
            db.flush()

            statuses.append(
                EventIngestionResponse.EventStatus(
                    event_id=event.event_id,
                    status="accepted",
                    message="",
                )
            )
            accepted_count += 1

        except Exception as e:
            logger.exception(f"Failed to ingest event {event.event_id}: {e}")
            statuses.append(
                EventIngestionResponse.EventStatus(
                    event_id=event.event_id,
                    status="rejected",
                    message=f"Validation failed: {str(e)[:100]}",
                )
            )
            rejected_count += 1

    # Commit all accepted events atomically
    try:
        db.commit()
    except Exception as e:
        logger.exception(f"Commit failed: {e}")
        db.rollback()
        # Mark all as rejected if commit fails
        return EventIngestionResponse(
            total=len(events),
            accepted=0,
            duplicates=0,
            rejected=len(events),
            events=[
                EventIngestionResponse.EventStatus(
                    event_id=s.event_id,
                    status="rejected",
                    message="Database commit failed; entire batch rolled back",
                )
                for s in statuses
            ],
        )

    return EventIngestionResponse(
        total=len(events),
        accepted=accepted_count,
        duplicates=duplicate_count,
        rejected=rejected_count,
        events=statuses,
    )
