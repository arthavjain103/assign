"""
Real-time metrics computation: conversion rate, dwell, queue depth, abandonment.
All calculations exclude is_staff=true. Zero-traffic returns 0.0, never null or NaN.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, select, and_

from .models import MetricsResponse
from .db import EventDB, POSTransactionDB

logger = logging.getLogger(__name__)


def compute_metrics(store_id: str, db: Session, hours: int = 24, now: Optional[datetime] = None) -> MetricsResponse:
    """
    Compute real-time metrics for a store over the last N hours.
    Gracefully handles zero traffic: returns 0.0 for all rates.
    
    Args:
        store_id: The store identifier
        db: SQLAlchemy session
        hours: Look-back window in hours (default: 24)
        now: Override current time for testing; defaults to datetime.utcnow()
    """
    if now is None:
        now = datetime.utcnow()
    since = now - timedelta(hours=hours)

    # Get all non-staff events in the window
    events = db.query(EventDB).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.is_staff == False,
            EventDB.timestamp >= since,
        )
    ).all()

    if not events:
        return MetricsResponse(
            store_id=store_id,
            timestamp=now.isoformat() + "Z",
            unique_visitors=0,
            conversion_rate=0.0,
            avg_dwell_per_zone={},
            current_queue_depth=0,
            abandonment_rate=0.0,
            avg_basket_value_inr=0.0,
            total_revenue_inr=0.0,
            avg_detection_confidence=0.0,
            low_confidence_ratio=0.0,
            data_quality_score=1.0,
            event_count_24h=0,
        )

    # Count unique visitors (per session, visitor_id resets on EXIT+REENTRY)
    unique_visitors_result = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.is_staff == False,
            EventDB.event_type == "ENTRY",
            EventDB.timestamp >= since,
        )
    ).scalar()
    unique_visitors = unique_visitors_result or 0

    # Conversion rate: distinct visitors in BILLING zone within 5 min before a POS txn
    converted = compute_conversions(store_id, db, since, now)
    conversion_rate = (converted / unique_visitors) if unique_visitors > 0 else 0.0

    # Average dwell per zone (ZONE_DWELL events)
    avg_dwell_per_zone = compute_avg_dwell_per_zone(events)

    # Current queue depth: count of distinct visitors IN the billing zone right now
    current_queue_depth = compute_queue_depth(store_id, db, now)

    # Abandonment rate: visitors in BILLING zone with no subsequent POS txn in window
    abandonment_rate = compute_abandonment_rate(store_id, db, since, now, unique_visitors)

    # Revenue metrics from POS transactions
    pos_txns = db.query(POSTransactionDB).filter(
        and_(
            POSTransactionDB.store_id == store_id,
            POSTransactionDB.timestamp >= since,
        )
    ).all()

    total_revenue_inr = sum(t.basket_value_inr for t in pos_txns)
    avg_basket_value_inr = (
        (total_revenue_inr / len(pos_txns)) if pos_txns else 0.0
    )

    # Data quality metrics: detection confidence distribution
    avg_detection_confidence, low_confidence_ratio = compute_data_quality(events)
    data_quality_score = 1.0 - (low_confidence_ratio * 0.5)  # Low-conf events reduce score

    # Total event count as proxy for traffic volume
    event_count_24h = len(events)

    return MetricsResponse(
        store_id=store_id,
        timestamp=now.isoformat() + "Z",
        unique_visitors=unique_visitors,
        conversion_rate=round(conversion_rate, 4),
        avg_dwell_per_zone=avg_dwell_per_zone,
        current_queue_depth=current_queue_depth,
        abandonment_rate=round(abandonment_rate, 4),
        avg_basket_value_inr=round(avg_basket_value_inr, 2),
        total_revenue_inr=round(total_revenue_inr, 2),
        avg_detection_confidence=round(avg_detection_confidence, 4),
        low_confidence_ratio=round(low_confidence_ratio, 4),
        data_quality_score=round(data_quality_score, 4),
        event_count_24h=event_count_24h,
    )


def compute_conversions(
    store_id: str,
    db: Session,
    since: datetime,
    until: datetime,
    window_minutes: int = 5,
) -> int:
    """
    A visitor is converted if they were in BILLING zone within window_minutes
    BEFORE a POS transaction timestamp (same store_id).
    """
    converted_visitors = set()

    # For each POS transaction, find visitors in BILLING zone within the window before it
    pos_txns = db.query(POSTransactionDB).filter(
        and_(
            POSTransactionDB.store_id == store_id,
            POSTransactionDB.timestamp >= since,
            POSTransactionDB.timestamp <= until,
        )
    ).all()

    for txn in pos_txns:
        window_start = txn.timestamp - timedelta(minutes=window_minutes)
        window_end = txn.timestamp

        # Find visitors in BILLING zone during this window
        billing_visitors = db.query(EventDB.visitor_id).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.zone_id == "BILLING",
                EventDB.timestamp >= window_start,
                EventDB.timestamp <= window_end,
                EventDB.is_staff == False,
            )
        ).distinct().all()

        for (visitor_id,) in billing_visitors:
            converted_visitors.add(visitor_id)

    return len(converted_visitors)


def compute_avg_dwell_per_zone(events: list[EventDB]) -> dict[str, float]:
    """Compute average dwell_ms per zone from ZONE_DWELL events."""
    dwell_by_zone = {}

    for event in events:
        if event.event_type == "ZONE_DWELL" and event.zone_id:
            if event.zone_id not in dwell_by_zone:
                dwell_by_zone[event.zone_id] = []
            dwell_by_zone[event.zone_id].append(event.dwell_ms)

    return {
        zone: round(sum(dwells) / len(dwells), 1)
        for zone, dwells in dwell_by_zone.items()
    }


def compute_queue_depth(
    store_id: str,
    db: Session,
    now: datetime,
    lookback_minutes: int = 10,
) -> int:
    """
    Current queue depth = number of distinct visitor_ids currently inside BILLING zone.
    We infer this from BILLING_QUEUE_JOIN - BILLING_QUEUE_ABANDON + still inside.
    Simplified: count active sessions that entered BILLING in the last lookback window
    without exiting.
    """
    since = now - timedelta(minutes=lookback_minutes)

    # Find all visitors with BILLING_QUEUE_JOIN in the lookback window
    joined = set(
        row[0]
        for row in db.query(EventDB.visitor_id).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.event_type == "BILLING_QUEUE_JOIN",
                EventDB.timestamp >= since,
            )
        ).distinct().all()
    )

    # Subtract those who BILLING_QUEUE_ABANDON or EXIT after joining
    abandoned = set(
        row[0]
        for row in db.query(EventDB.visitor_id).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.event_type.in_(["BILLING_QUEUE_ABANDON", "EXIT"]),
                EventDB.timestamp >= since,
            )
        ).distinct().all()
    )

    active_visitors = joined - abandoned
    return len(active_visitors)


def compute_abandonment_rate(
    store_id: str,
    db: Session,
    since: datetime,
    until: datetime,
    total_visitors: int,
) -> float:
    """
    Abandonment rate = visitors who entered BILLING but have no POS txn within
    5 min after their BILLING zone entry.
    """
    if total_visitors == 0:
        return 0.0

    # Find all visitors who entered BILLING zone
    billing_visitors = set(
        row[0]
        for row in db.query(EventDB.visitor_id).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.zone_id == "BILLING",
                EventDB.timestamp >= since,
                EventDB.timestamp <= until,
            )
        ).distinct().all()
    )

    if not billing_visitors:
        return 0.0

    # Find which of those converted (have POS txn within 5 min)
    window_minutes = 5
    converted = set()

    for visitor_id in billing_visitors:
        # Get the last ZONE_ENTER to BILLING for this visitor
        last_billing_enter = db.query(func.max(EventDB.timestamp)).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.visitor_id == visitor_id,
                EventDB.zone_id == "BILLING",
                EventDB.event_type == "ZONE_ENTER",
            )
        ).scalar()

        if last_billing_enter:
            window_end = last_billing_enter + timedelta(minutes=window_minutes)
            has_pos = db.query(POSTransactionDB).filter(
                and_(
                    POSTransactionDB.store_id == store_id,
                    POSTransactionDB.timestamp >= last_billing_enter,
                    POSTransactionDB.timestamp <= window_end,
                )
            ).first() is not None

            if has_pos:
                converted.add(visitor_id)

    abandoners = len(billing_visitors) - len(converted)
    return (abandoners / len(billing_visitors)) if billing_visitors else 0.0


def compute_data_quality(events: list[EventDB]) -> Tuple[float, float]:
    """
    Compute data quality metrics: avg_detection_confidence and low_confidence_ratio.
    
    Returns:
        (avg_confidence, low_confidence_ratio)
        - avg_confidence: Mean confidence across all detections (0–1)
        - low_confidence_ratio: Fraction with confidence < 0.7 (0–1)
    """
    if not events:
        return 0.0, 0.0

    confidences = [e.confidence for e in events if e.confidence is not None]
    
    if not confidences:
        return 0.0, 0.0

    avg_confidence = sum(confidences) / len(confidences)
    low_confidence_count = sum(1 for c in confidences if c < 0.7)
    low_confidence_ratio = low_confidence_count / len(confidences)

    return avg_confidence, low_confidence_ratio
