# PROMPT: Test funnel calculation with re-entry deduplication and drop-off percentages
# CHANGES MADE: Added tests for entry->zone->billing->purchase flow with re-entry handling

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db import EventDB, POSTransactionDB, engine, SessionLocal, init_db
from app.models import Event, EventType
from app.funnel import compute_funnel
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
    session.commit()


def test_funnel_basic_flow(db: Session):
    """Test funnel with basic entry -> zone -> billing -> purchase."""
    now = datetime.utcnow()
    store_id = "STORE_FUNNEL_001"

    # 5 entries
    for i in range(5):
        db.add(EventDB(
            event_id=f"entry-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_{i}",
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({}),
        ))

    # 4 zone visits (1 dropped)
    for i in range(4):
        db.add(EventDB(
            event_id=f"zone-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_{i}",
            event_type="ZONE_ENTER",
            timestamp=now + timedelta(minutes=1),
            zone_id="SKINCARE",
            is_staff=False,
            confidence=0.9,
            metadata=json.dumps({}),
        ))

    # 3 billing visits (1 dropped)
    for i in range(3):
        db.add(EventDB(
            event_id=f"billing-{i}",
            store_id=store_id,
            camera_id="CAM_CHECKOUT",
            visitor_id=f"VIS_{i}",
            event_type="ZONE_ENTER",
            timestamp=now + timedelta(minutes=5),
            zone_id="BILLING",
            is_staff=False,
            confidence=0.92,
            metadata=json.dumps({}),
        ))

    # 2 purchases (1 abandoned)
    for i in range(2):
        db.add(POSTransactionDB(
            transaction_id=f"TXN_{i}",
            store_id=store_id,
            timestamp=now + timedelta(minutes=6),
            basket_value_inr=1000.0 + i * 100,
        ))

    db.commit()

    funnel = compute_funnel(store_id, db)
    assert len(funnel.steps) == 4
    assert funnel.steps[0].step == "ENTRY"
    assert funnel.steps[0].count == 5
    assert funnel.steps[1].step == "ZONE_VISIT"
    assert funnel.steps[1].count == 4
    assert funnel.steps[2].step == "BILLING_QUEUE"
    assert funnel.steps[2].count == 3
    assert funnel.steps[3].step == "PURCHASE"
    assert funnel.steps[3].count == 2


def test_funnel_drop_off_percentages(db: Session):
    """Test that drop-off percentages are calculated correctly."""
    now = datetime.utcnow()
    store_id = "STORE_FUNNEL_002"

    # 10 entries
    for i in range(10):
        db.add(EventDB(
            event_id=f"entry-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_{i}",
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({}),
        ))

    # 5 zone visits (50% drop)
    for i in range(5):
        db.add(EventDB(
            event_id=f"zone-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_{i}",
            event_type="ZONE_ENTER",
            timestamp=now + timedelta(minutes=1),
            zone_id="SKINCARE",
            is_staff=False,
            confidence=0.9,
            metadata=json.dumps({}),
        ))

    db.commit()

    funnel = compute_funnel(store_id, db)
    assert funnel.steps[0].drop_off_percent == 0.0  # First step, no drop-off
    assert funnel.steps[1].drop_off_percent == 50.0  # 50% dropped from entry


def test_funnel_excludes_staff(db: Session):
    """Test that staff events are excluded from funnel."""
    now = datetime.utcnow()
    store_id = "STORE_FUNNEL_003"

    # 5 customer entries
    for i in range(5):
        db.add(EventDB(
            event_id=f"cust-entry-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_CUST_{i}",
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({}),
        ))

    # 3 staff entries (should be ignored)
    for i in range(3):
        db.add(EventDB(
            event_id=f"staff-entry-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_STAFF_{i}",
            event_type="ENTRY",
            timestamp=now,
            is_staff=True,
            confidence=0.95,
            metadata=json.dumps({}),
        ))

    db.commit()

    funnel = compute_funnel(store_id, db)
    assert funnel.steps[0].count == 5  # Only customers


def test_funnel_empty_store(db: Session):
    """Test funnel for store with no events."""
    funnel = compute_funnel("STORE_EMPTY", db)
    assert funnel.steps[0].count == 0
    assert all(s.count == 0 for s in funnel.steps)


def test_funnel_reentry_not_double_counted(db: Session):
    """Test that re-entries (EXIT then ENTRY) don't create new funnel entries."""
    now = datetime.utcnow()
    store_id = "STORE_FUNNEL_004"

    # First session: VIS_1 enters
    db.add(EventDB(
        event_id="entry-1",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_1",
        event_type="ENTRY",
        timestamp=now,
        is_staff=False,
        confidence=0.95,
        metadata=json.dumps({}),
    ))

    # VIS_1 exits
    db.add(EventDB(
        event_id="exit-1",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_1",
        event_type="EXIT",
        timestamp=now + timedelta(minutes=10),
        is_staff=False,
        confidence=0.95,
        metadata=json.dumps({}),
    ))

    # Re-entry: VIS_1 enters again (but same visitor_id means new session)
    # In real life, re-entry would be detected and marked as REENTRY, not ENTRY
    db.add(EventDB(
        event_id="reentry-1",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_1",
        event_type="REENTRY",
        timestamp=now + timedelta(minutes=20),
        is_staff=False,
        confidence=0.85,
        metadata=json.dumps({}),
    ))

    db.commit()

    funnel = compute_funnel(store_id, db)
    # Should only count 1 ENTRY event
    assert funnel.steps[0].count == 1


def test_funnel_zone_visit_counting(db: Session):
    """Test that zone visits are counted by distinct visitor_id."""
    now = datetime.utcnow()
    store_id = "STORE_FUNNEL_005"

    # 3 visitors enter
    for i in range(3):
        db.add(EventDB(
            event_id=f"entry-{i}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_{i}",
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({}),
        ))

    # Each visitor has multiple zone enters (VIS_0 visits 2 zones)
    db.add(EventDB(
        event_id="zone-1",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_0",
        event_type="ZONE_ENTER",
        timestamp=now + timedelta(minutes=1),
        zone_id="SKINCARE",
        is_staff=False,
        confidence=0.9,
        metadata=json.dumps({}),
    ))

    db.add(EventDB(
        event_id="zone-2",
        store_id=store_id,
        camera_id="CAM_01",
        visitor_id="VIS_0",
        event_type="ZONE_ENTER",
        timestamp=now + timedelta(minutes=2),
        zone_id="MAKEUP",
        is_staff=False,
        confidence=0.9,
        metadata=json.dumps({}),
    ))

    # VIS_1 and VIS_2 each visit one zone
    for i in range(1, 3):
        db.add(EventDB(
            event_id=f"zone-{i+2}",
            store_id=store_id,
            camera_id="CAM_01",
            visitor_id=f"VIS_{i}",
            event_type="ZONE_ENTER",
            timestamp=now + timedelta(minutes=1),
            zone_id="SKINCARE",
            is_staff=False,
            confidence=0.9,
            metadata=json.dumps({}),
        ))

    db.commit()

    funnel = compute_funnel(store_id, db)
    # Should count distinct visitors, not zone visits
    assert funnel.steps[1].count == 3
