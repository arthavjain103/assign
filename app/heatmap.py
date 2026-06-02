"""
Heatmap computation: zone visit frequency + average dwell.
Intensity normalized 0–100. Flags low-confidence if <20 sessions in window.
"""
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from .models import HeatmapResponse, HeatmapZone
from .db import EventDB

logger = logging.getLogger(__name__)


def compute_heatmap(store_id: str, db: Session, hours: int = 24) -> HeatmapResponse:
    """
    Compute heatmap: zone visit counts and average dwell times.
    Normalizes intensity 0–100 based on max visit count.
    Flags low confidence if <20 total sessions.
    """
    now = datetime.utcnow()
    since = now - timedelta(hours=hours)

    # Get all zone enter/dwell events in the window
    events = db.query(EventDB).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.zone_id.isnot(None),
            EventDB.event_type.in_(["ZONE_ENTER", "ZONE_DWELL"]),
            EventDB.is_staff == False,
            EventDB.timestamp >= since,
        )
    ).all()

    # Group by zone
    zone_stats = {}
    for event in events:
        if event.zone_id not in zone_stats:
            zone_stats[event.zone_id] = {
                "visit_count": 0,
                "dwell_times": [],
            }

        if event.event_type == "ZONE_ENTER":
            zone_stats[event.zone_id]["visit_count"] += 1
        elif event.event_type == "ZONE_DWELL":
            zone_stats[event.zone_id]["dwell_times"].append(event.dwell_ms)

    # Find max visit count for normalization
    max_visits = max(
        (stats["visit_count"] for stats in zone_stats.values()),
        default=1,
    )

    # Build heatmap zones
    zones = []
    for zone_id, stats in sorted(zone_stats.items()):
        avg_dwell = (
            sum(stats["dwell_times"]) / len(stats["dwell_times"])
            if stats["dwell_times"]
            else 0.0
        )

        intensity = (
            round(100 * stats["visit_count"] / max_visits, 1) if max_visits > 0 else 0.0
        )

        zones.append(
            HeatmapZone(
                zone_id=zone_id,
                visit_count=stats["visit_count"],
                avg_dwell_ms=round(avg_dwell, 1),
                intensity=intensity,
            )
        )

    # Total sessions for confidence flag
    total_sessions = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type == "ENTRY",
            EventDB.is_staff == False,
            EventDB.timestamp >= since,
        )
    ).scalar() or 0

    data_confidence = total_sessions >= 20

    return HeatmapResponse(
        store_id=store_id,
        timestamp=now.isoformat() + "Z",
        zones=zones,
        data_confidence=data_confidence,
    )
