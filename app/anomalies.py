"""
Anomaly detection: queue spike, conversion drop vs 7-day avg, dead zone.
All anomalies are open-hours aware (dead zone only fires while store open).
"""
from datetime import datetime, timedelta
import logging
import json

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from .models import AnomaliesResponse, Anomaly
from .db import EventDB, POSTransactionDB, StoreLayoutDB

logger = logging.getLogger(__name__)


def compute_anomalies(store_id: str, db: Session) -> AnomaliesResponse:
    """
    Detect active anomalies: queue spike, conversion drop, dead zone.
    All checks respect store open hours.
    """
    now = datetime.utcnow()
    anomalies = []

    # Load store layout for open hours
    store_layout = db.query(StoreLayoutDB).filter(
        StoreLayoutDB.store_id == store_id
    ).first()

    open_hours = {}
    if store_layout:
        open_hours = json.loads(store_layout.open_hours or "{}")

    # Check if store is open now
    is_open_now = is_store_open(now, open_hours)

    # 1. Queue spike
    queue_spike_anomaly = check_queue_spike(store_id, db, now)
    if queue_spike_anomaly:
        anomalies.append(queue_spike_anomaly)

    # 2. Conversion drop (vs 7-day average)
    if is_open_now:
        conversion_drop_anomaly = check_conversion_drop(store_id, db, now)
        if conversion_drop_anomaly:
            anomalies.append(conversion_drop_anomaly)

    # 3. Dead zone (only flag if store is open)
    if is_open_now:
        dead_zone_anomalies = check_dead_zones(store_id, db, now)
        anomalies.extend(dead_zone_anomalies)

    return AnomaliesResponse(
        store_id=store_id,
        timestamp=now.isoformat() + "Z",
        anomalies=anomalies,
    )


def is_store_open(now: datetime, open_hours: dict[str, tuple[str, str]]) -> bool:
    """Check if store is open at the given datetime based on open_hours."""
    if not open_hours:
        return True  # Assume open if no schedule

    day_name = now.strftime("%a").lower()  # "mon", "tue", etc.
    if day_name not in open_hours:
        return False  # Assume closed if not in schedule

    try:
        open_time_str, close_time_str = open_hours[day_name]
        open_time = datetime.strptime(open_time_str, "%H:%M").time()
        close_time = datetime.strptime(close_time_str, "%H:%M").time()

        current_time = now.time()
        return open_time <= current_time <= close_time
    except Exception:
        return True


def check_queue_spike(store_id: str, db: Session, now: datetime) -> Anomaly | None:
    """
    Queue spike: current queue depth significantly above 15-min avg, or threshold.
    """
    # Current queue depth
    lookback = now - timedelta(minutes=10)
    current_queue = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type == "BILLING_QUEUE_JOIN",
            EventDB.timestamp >= lookback,
        )
    ).scalar() or 0

    # 15-min historical average
    hist_start = now - timedelta(minutes=30)
    hist_end = now - timedelta(minutes=15)
    hist_queue = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type == "BILLING_QUEUE_JOIN",
            EventDB.timestamp >= hist_start,
            EventDB.timestamp <= hist_end,
        )
    ).scalar() or 0

    # Threshold: current > historical average + 50% OR > 5 people
    if current_queue > max(hist_queue * 1.5, 5):
        return Anomaly(
            anomaly_type="QUEUE_SPIKE",
            severity="WARN",
            message=f"Queue depth spiked to {current_queue} (historical avg: {hist_queue:.0f})",
            suggested_action="Increase checkout staff",
        )

    return None


def check_conversion_drop(store_id: str, db: Session, now: datetime) -> Anomaly | None:
    """
    Conversion drop: today's rate < 7-day average by >20%.
    """
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Today's conversion rate
    today_entries = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type == "ENTRY",
            EventDB.is_staff == False,
            EventDB.timestamp >= today_start,
        )
    ).scalar() or 0

    today_converted = count_converted_today(store_id, db, today_start, now)
    today_rate = (today_converted / today_entries) if today_entries > 0 else 0.0

    # 7-day average
    week_start = now - timedelta(days=7)
    week_entries = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type == "ENTRY",
            EventDB.is_staff == False,
            EventDB.timestamp >= week_start,
        )
    ).scalar() or 0

    week_converted = count_converted_in_range(store_id, db, week_start, now)
    week_rate = (week_converted / week_entries) if week_entries > 0 else 0.0

    # Flag if insufficient history
    if week_entries < 50:
        return Anomaly(
            anomaly_type="CONVERSION_DROP",
            severity="INFO",
            message=f"Insufficient history (only {week_entries} week entries); cannot compare",
            suggested_action="Continue monitoring; anomaly will activate after 7 days",
        )

    # Check for drop
    if week_rate > 0 and today_rate < week_rate * 0.8:  # 20% drop
        return Anomaly(
            anomaly_type="CONVERSION_DROP",
            severity="WARN",
            message=f"Conversion dropped to {today_rate:.1%} (7-day avg: {week_rate:.1%})",
            suggested_action="Review merchandising and checkout experience",
        )

    return None


def check_dead_zones(store_id: str, db: Session, now: datetime) -> list[Anomaly]:
    """
    Dead zone: no ZONE_ENTER in a zone for 30+ minutes while store is open.
    """
    anomalies = []
    lookback = now - timedelta(minutes=30)

    # Get all zones that have ANY activity in the store
    all_zones = db.query(EventDB.zone_id).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.zone_id.isnot(None),
        )
    ).distinct().all()

    for (zone_id,) in all_zones:
        if not zone_id:
            continue

        # Check last ZONE_ENTER for this zone
        last_enter = db.query(func.max(EventDB.timestamp)).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.zone_id == zone_id,
                EventDB.event_type == "ZONE_ENTER",
            )
        ).scalar()

        if last_enter is None or last_enter < lookback:
            anomalies.append(
                Anomaly(
                    anomaly_type="DEAD_ZONE",
                    severity="INFO",
                    message=f"Zone '{zone_id}' has no foot traffic for 30+ minutes",
                    suggested_action="Check zone visibility or re-arrange stock",
                )
            )

    return anomalies


def count_converted_today(
    store_id: str,
    db: Session,
    today_start: datetime,
    now: datetime,
    window_minutes: int = 5,
) -> int:
    """Count distinct visitors in BILLING zone within 5 min before a POS txn (today)."""
    converted = set()

    pos_txns = db.query(POSTransactionDB).filter(
        and_(
            POSTransactionDB.store_id == store_id,
            POSTransactionDB.timestamp >= today_start,
            POSTransactionDB.timestamp <= now,
        )
    ).all()

    for txn in pos_txns:
        window_start = txn.timestamp - timedelta(minutes=window_minutes)
        billing_visitors = db.query(EventDB.visitor_id).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.zone_id == "BILLING",
                EventDB.timestamp >= window_start,
                EventDB.timestamp <= txn.timestamp,
            )
        ).distinct().all()

        for (visitor_id,) in billing_visitors:
            converted.add(visitor_id)

    return len(converted)


def count_converted_in_range(
    store_id: str,
    db: Session,
    since: datetime,
    until: datetime,
    window_minutes: int = 5,
) -> int:
    """Count distinct visitors in BILLING zone within 5 min before a POS txn (range)."""
    converted = set()

    pos_txns = db.query(POSTransactionDB).filter(
        and_(
            POSTransactionDB.store_id == store_id,
            POSTransactionDB.timestamp >= since,
            POSTransactionDB.timestamp <= until,
        )
    ).all()

    for txn in pos_txns:
        window_start = txn.timestamp - timedelta(minutes=window_minutes)
        billing_visitors = db.query(EventDB.visitor_id).filter(
            and_(
                EventDB.store_id == store_id,
                EventDB.zone_id == "BILLING",
                EventDB.timestamp >= window_start,
                EventDB.timestamp <= txn.timestamp,
            )
        ).distinct().all()

        for (visitor_id,) in billing_visitors:
            converted.add(visitor_id)

    return len(converted)
