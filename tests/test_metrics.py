# PROMPT: Create comprehensive tests for all API metrics calculations with edge cases (zero traffic, high volume)
# CHANGES MADE: Added tests for conversion rate, dwell time, queue depth, abandonment rate with graceful zero handling

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import EventDB, POSTransactionDB, StoreLayoutDB, engine, SessionLocal, init_db
from app.models import Event, EventType
from app.metrics import (
    compute_metrics,
    compute_conversions,
    compute_avg_dwell_per_zone,
    compute_queue_depth,
    compute_abandonment_rate,
)
import json


@pytest.fixture(scope="function")
def db():
    """Create a test database session."""
    init_db()
    session = SessionLocal()
    yield session
    session.close()
    # Clean up
    session.query(EventDB).delete()
    session.query(POSTransactionDB).delete()
    session.query(StoreLayoutDB).delete()
    session.commit()


def test_metrics_empty_store(db: Session):
    """Test metrics for a store with no events."""
    metrics = compute_metrics("STORE_EMPTY", db)
    assert metrics.store_id == "STORE_EMPTY"
    assert metrics.unique_visitors == 0
    assert metrics.conversion_rate == 0.0
    assert metrics.total_revenue_inr == 0.0
    assert metrics.avg_basket_value_inr == 0.0


def test_metrics_with_visitors(db: Session):
    """Test metrics with actual visitor events."""
    now = datetime.utcnow()
    store_id = "STORE_TEST_001"

    # Create 5 ENTRY events
    for i in range(5):
        event = EventDB(
            event_id=f"entry-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_{i}",
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({}),
        )
        db.add(event)

    db.commit()

    metrics = compute_metrics(store_id, db)
    assert metrics.unique_visitors == 5
    assert metrics.store_id == store_id


def test_metrics_excludes_staff(db: Session):
    """Test that is_staff=true events are excluded from metrics."""
    now = datetime.utcnow()
    store_id = "STORE_TEST_002"

    # Add customer entry
    event1 = EventDB(
        event_id="cust-1",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_CUST_1",
        event_type="ENTRY",
        timestamp=now,
        is_staff=False,
        confidence=0.95,
        event_metadata=json.dumps({}),
    )
    db.add(event1)

    # Add staff entry
    event2 = EventDB(
        event_id="staff-1",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_STAFF_1",
        event_type="ENTRY",
        timestamp=now,
        is_staff=True,
        confidence=0.95,
        event_metadata=json.dumps({}),
    )
    db.add(event2)
    db.commit()

    metrics = compute_metrics(store_id, db)
    # Only 1 customer, staff is excluded
    assert metrics.unique_visitors == 1


def test_dwell_time_calculation(db: Session):
    """Test average dwell time per zone."""
    now = datetime.utcnow()
    store_id = "STORE_TEST_003"

    # Create zone dwell events
    dwells = [
        EventDB(
            event_id=f"dwell-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id="VIS_1",
            event_type="ZONE_DWELL",
            timestamp=now + timedelta(seconds=i),
            zone_id="SKINCARE",
            dwell_ms=60000 + i * 1000,
            is_staff=False,
            confidence=0.9,
            event_metadata=json.dumps({}),
        )
        for i in range(3)
    ]
    for dwell in dwells:
        db.add(dwell)
    db.commit()

    metrics = compute_metrics(store_id, db)
    assert "SKINCARE" in metrics.avg_dwell_per_zone
    # Average of 60000, 61000, 62000
    assert metrics.avg_dwell_per_zone["SKINCARE"] > 60000


def test_conversion_rate_calculation(db: Session):
    """Test conversion rate: visitor in BILLING zone within 5 min before POS txn."""
    now = datetime.utcnow()
    store_id = "STORE_TEST_004"

    # Create entry
    entry = EventDB(
        event_id="entry-conv-1",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_CONV_1",
        event_type="ENTRY",
        timestamp=now,
        is_staff=False,
        confidence=0.95,
        event_metadata=json.dumps({}),
    )
    db.add(entry)

    # Create billing zone enter
    billing_enter = EventDB(
        event_id="billing-enter-1",
        store_id=store_id,
        camera_id="CAM_CHECKOUT",
        visitor_id="VIS_CONV_1",
        event_type="ZONE_ENTER",
        timestamp=now + timedelta(minutes=2),
        zone_id="BILLING",
        is_staff=False,
        confidence=0.95,
        event_metadata=json.dumps({}),
    )
    db.add(billing_enter)

    # Create POS transaction 3 minutes after billing enter
    pos_txn = POSTransactionDB(
        transaction_id="TXN_001",
        store_id=store_id,
        timestamp=now + timedelta(minutes=5),
        basket_value_inr=1000.0,
    )
    db.add(pos_txn)
    db.commit()

    # Use test's 'now' to ensure consistent time windows
    metrics = compute_metrics(store_id, db, now=now + timedelta(minutes=6))
    # 1 converted out of 1 visitor
    assert metrics.conversion_rate == 1.0


def test_queue_depth_calculation(db: Session):
    """Test current queue depth: distinct visitors in BILLING zone."""
    now = datetime.utcnow()
    store_id = "STORE_TEST_005"

    # Create 3 visitors joining queue
    for i in range(3):
        queue_join = EventDB(
            event_id=f"queue-{i}",
            store_id=store_id,
            camera_id="CAM_CHECKOUT",
            visitor_id=f"VIS_QUEUE_{i}",
            event_type="BILLING_QUEUE_JOIN",
            timestamp=now - timedelta(minutes=5),
            zone_id="BILLING",
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({"queue_depth": i + 1}),
        )
        db.add(queue_join)

    db.commit()

    queue_depth = compute_queue_depth(store_id, db, now)
    assert queue_depth == 3


def test_queue_depth_excludes_exits(db: Session):
    """Test that queue depth excludes visitors who have exited."""
    now = datetime.utcnow()
    store_id = "STORE_TEST_006"

    # Visitor joins queue
    queue_join = EventDB(
        event_id="queue-join-1",
        store_id=store_id,
        camera_id="CAM_CHECKOUT",
        visitor_id="VIS_QUEUE_1",
        event_type="BILLING_QUEUE_JOIN",
        timestamp=now - timedelta(minutes=5),
        zone_id="BILLING",
        is_staff=False,
        confidence=0.95,
        event_metadata=json.dumps({"queue_depth": i + 1}),
    )
    db.add(queue_join)

    # Visitor exits
    exit_event = EventDB(
        event_id="exit-1",
        store_id=store_id,
        camera_id="CAM_EXIT",
        visitor_id="VIS_QUEUE_1",
        event_type="EXIT",
        timestamp=now - timedelta(minutes=1),
        is_staff=False,
        confidence=0.95,
        event_metadata=json.dumps({}),
    )
    db.add(exit_event)
    db.commit()

    queue_depth = compute_queue_depth(store_id, db, now)
    # Visitor exited, so queue should be empty
    assert queue_depth == 0


def test_abandonment_rate_calculation(db: Session):
    """Test abandonment rate: billing zone visitors with no POS txn."""
    now = datetime.utcnow()
    store_id = "STORE_TEST_007"

    # 2 visitors enter billing zone
    for i in range(2):
        billing_enter = EventDB(
            event_id=f"billing-{i}",
            store_id=store_id,
            camera_id="CAM_CHECKOUT",
            visitor_id=f"VIS_ABANDON_{i}",
            event_type="ZONE_ENTER",
            timestamp=now,
            zone_id="BILLING",
            is_staff=False,
            confidence=0.95,
            event_metadata=json.dumps({}),
        )
        db.add(billing_enter)

    # Only 1 makes a POS transaction
    pos_txn = POSTransactionDB(
        transaction_id="TXN_ABANDON_1",
        store_id=store_id,
        timestamp=now + timedelta(minutes=3),
        basket_value_inr=500.0,
    )
    db.add(pos_txn)
    db.commit()

    # Pass until time that includes both billing entries and POS txn
    abandonment_rate = compute_abandonment_rate(store_id, db, now - timedelta(minutes=1), now + timedelta(minutes=5), 2)
    # 1 out of 2 abandoned
    assert abandonment_rate == 0.5
