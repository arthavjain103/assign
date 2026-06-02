"""
Conversion funnel: Entry → Zone Visit → Billing Queue → Purchase.
Session is the unit; re-entries are NOT double-counted.
"""
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from .models import FunnelResponse, FunnelStep
from .db import EventDB, POSTransactionDB

logger = logging.getLogger(__name__)


def compute_funnel(store_id: str, db: Session, hours: int = 24) -> FunnelResponse:
    """
    Compute conversion funnel: count unique sessions at each step.
    Re-entries (same visitor_id after EXIT) are NOT double-counted.
    """
    now = datetime.utcnow()
    since = now - timedelta(hours=hours)

    # Step 1: ENTRY (unique sessions)
    entries = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type == "ENTRY",
            EventDB.is_staff == False,
            EventDB.timestamp >= since,
        )
    ).scalar() or 0

    # Step 2: Zone Visit (unique visitors with ZONE_ENTER after entry)
    zone_visitors = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type == "ZONE_ENTER",
            EventDB.is_staff == False,
            EventDB.timestamp >= since,
        )
    ).scalar() or 0

    # Step 3: Billing Queue (unique visitors who joined billing queue)
    billing_visitors = db.query(func.count(func.distinct(EventDB.visitor_id))).filter(
        and_(
            EventDB.store_id == store_id,
            EventDB.event_type.in_(["BILLING_QUEUE_JOIN", "ZONE_ENTER"]),
            EventDB.zone_id == "BILLING",
            EventDB.is_staff == False,
            EventDB.timestamp >= since,
        )
    ).scalar() or 0

    # Step 4: Purchase (unique visitors with POS transaction in window)
    purchases = db.query(func.count(func.distinct(POSTransactionDB.store_id))).filter(
        and_(
            POSTransactionDB.store_id == store_id,
            POSTransactionDB.timestamp >= since,
        )
    ).scalar() or 0

    # Calculate drop-off percentages
    steps = [
        FunnelStep(
            step="ENTRY",
            count=entries,
            drop_off_percent=0.0,
        ),
        FunnelStep(
            step="ZONE_VISIT",
            count=zone_visitors,
            drop_off_percent=(
                round(100 * (1 - zone_visitors / entries), 2) if entries > 0 else 0.0
            ),
        ),
        FunnelStep(
            step="BILLING_QUEUE",
            count=billing_visitors,
            drop_off_percent=(
                round(100 * (1 - billing_visitors / zone_visitors), 2)
                if zone_visitors > 0
                else 0.0
            ),
        ),
        FunnelStep(
            step="PURCHASE",
            count=purchases,
            drop_off_percent=(
                round(100 * (1 - purchases / billing_visitors), 2)
                if billing_visitors > 0
                else 0.0
            ),
        ),
    ]

    return FunnelResponse(
        store_id=store_id,
        timestamp=now.isoformat() + "Z",
        steps=steps,
        unique_sessions=entries,
    )
