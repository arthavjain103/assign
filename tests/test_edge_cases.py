"""
Edge case tests for Store Intelligence detection pipeline.
Covers: re-entry deduplication, staff detection, group entry, queue abandonment, etc.
"""

import pytest
from datetime import datetime, timedelta
import json
from sqlalchemy.orm import Session

from app.db import EventDB, POSTransactionDB, engine, SessionLocal, init_db
from app.models import Event, EventType
from app.metrics import compute_metrics
from app.funnel import compute_funnel


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


class TestReEntryDeduplication:
    """Test that re-entries are correctly deduplicated in metrics and funnel."""

    def test_same_visitor_exit_and_reentry(self, db: Session):
        """
        Scenario: Visitor enters, exits, re-enters within 15 min.
        Expected: Should count as 1 unique visitor, not 2.
        """
        now = datetime.utcnow()
        store_id = "STORE_REENTRY_001"
        visitor_id = "VIS_001"

        # First entry
        db.add(EventDB(
            event_id="entry-1",
            store_id=store_id,
            camera_id="CAM_ENTRY",
            visitor_id=visitor_id,
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({}),
        ))

        # Exit
        db.add(EventDB(
            event_id="exit-1",
            store_id=store_id,
            camera_id="CAM_ENTRY",
            visitor_id=visitor_id,
            event_type="EXIT",
            timestamp=now + timedelta(minutes=5),
            is_staff=False,
            confidence=0.95,
            metadata=json.dumps({}),
        ))

        # Re-entry (same visitor_id due to re-ID)
        db.add(EventDB(
            event_id="entry-2",
            store_id=store_id,
            camera_id="CAM_ENTRY",
            visitor_id=visitor_id,
            event_type="ENTRY",
            timestamp=now + timedelta(minutes=10),
            is_staff=False,
            confidence=0.85,
            metadata=json.dumps({"reentry": True}),
        ))

        db.commit()

        # Metrics should count 1 unique visitor (re-entry is same session)
        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        assert metrics.unique_visitors == 1, "Re-entry should not increment unique_visitors"

        # Funnel should also count 1 entry
        funnel = compute_funnel(store_id, db, hours=24)
        assert funnel.steps[0].count == 1, "Funnel should deduplicate re-entries"

    def test_multiple_reentries_same_visitor(self, db: Session):
        """
        Scenario: Same visitor enters 3 times in 1 hour.
        Expected: All 3 entries recorded, but unique_visitors=1.
        """
        now = datetime.utcnow()
        store_id = "STORE_MULTI_REENTRY"
        visitor_id = "VIS_MULTI"

        for i in range(3):
            db.add(EventDB(
                event_id=f"entry-{i}",
                store_id=store_id,
                camera_id="CAM_ENTRY",
                visitor_id=visitor_id,
                event_type="ENTRY",
                timestamp=now + timedelta(minutes=i * 15),
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}) if i == 0 else json.dumps({"reentry": True}),
            ))

            if i < 2:
                db.add(EventDB(
                    event_id=f"exit-{i}",
                    store_id=store_id,
                    camera_id="CAM_ENTRY",
                    visitor_id=visitor_id,
                    event_type="EXIT",
                    timestamp=now + timedelta(minutes=i * 15 + 5),
                    is_staff=False,
                    confidence=0.9,
                    metadata=json.dumps({}),
                ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        assert metrics.unique_visitors == 1, "Multiple re-entries should not increase unique_visitors"


class TestStaffDetection:
    """Test that staff are correctly excluded from metrics."""

    def test_staff_excluded_from_metrics(self, db: Session):
        """
        Scenario: 5 customers + 2 staff enter. Metrics should only count 5.
        Expected: unique_visitors=5, not 7.
        """
        now = datetime.utcnow()
        store_id = "STORE_STAFF_TEST"

        # 5 customer entries
        for i in range(5):
            db.add(EventDB(
                event_id=f"cust-{i}",
                store_id=store_id,
                camera_id="CAM_ENTRY",
                visitor_id=f"CUST_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.95,
                metadata=json.dumps({}),
            ))

        # 2 staff entries
        for i in range(2):
            db.add(EventDB(
                event_id=f"staff-{i}",
                store_id=store_id,
                camera_id="CAM_ENTRY",
                visitor_id=f"STAFF_{i}",
                event_type="ENTRY",
                timestamp=now + timedelta(seconds=1),
                is_staff=True,
                confidence=0.98,
                metadata=json.dumps({"staff_zone": "billing"}),
            ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        assert metrics.unique_visitors == 5, "Staff should be excluded from unique_visitors count"

    def test_staff_queue_depth_exclusion(self, db: Session):
        """
        Scenario: 3 customers + 1 staff in billing zone simultaneously.
        Expected: queue_depth=3, not 4.
        """
        now = datetime.utcnow()
        store_id = "STORE_QUEUE_TEST"

        # 3 customers in billing
        for i in range(3):
            db.add(EventDB(
                event_id=f"cust-billing-{i}",
                store_id=store_id,
                camera_id="CAM_BILLING",
                visitor_id=f"CUST_{i}",
                event_type="ZONE_ENTER",
                zone_id="BILLING",
                timestamp=now,
                is_staff=False,
                confidence=0.92,
                metadata=json.dumps({}),
            ))

        # 1 staff in billing
        db.add(EventDB(
            event_id="staff-billing-1",
            store_id=store_id,
            camera_id="CAM_BILLING",
            visitor_id="STAFF_1",
            event_type="ZONE_ENTER",
            zone_id="BILLING",
            timestamp=now,
            is_staff=True,
            confidence=0.98,
            metadata=json.dumps({}),
        ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now)
        # queue_depth should reflect only customers, not staff
        assert metrics.current_queue_depth == 3, "Queue depth should exclude staff"


class TestGroupEntry:
    """Test correct handling of group entries."""

    def test_group_of_5_creates_5_entries(self, db: Session):
        """
        Scenario: A group of 5 people enters together (same frame_idx, track_id range).
        Expected: 5 separate ENTRY events, each creates a session.
        """
        now = datetime.utcnow()
        store_id = "STORE_GROUP_001"

        # Group of 5 enters in same second
        for i in range(5):
            db.add(EventDB(
                event_id=f"group-entry-{i}",
                store_id=store_id,
                camera_id="CAM_ENTRY",
                visitor_id=f"VIS_GROUP_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.88,
                metadata=json.dumps({"group_entry": True, "group_size": 5}),
            ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        assert metrics.unique_visitors == 5, "Group entry should create separate sessions per person"

        funnel = compute_funnel(store_id, db, hours=24)
        assert funnel.steps[0].count == 5, "Funnel should count 5 entries for group of 5"


class TestBillingQueueAbandonment:
    """Test abandonment detection (entered billing but no purchase)."""

    def test_zone_exit_without_purchase_counts_as_abandon(self, db: Session):
        """
        Scenario: Visitor enters billing zone but exits without purchasing.
        Expected: Abandonment flag should be set.
        """
        now = datetime.utcnow()
        store_id = "STORE_ABANDON_001"
        visitor_id = "VIS_ABANDON_1"

        # Entry to billing zone
        db.add(EventDB(
            event_id="billing-enter-1",
            store_id=store_id,
            camera_id="CAM_BILLING",
            visitor_id=visitor_id,
            event_type="ZONE_ENTER",
            zone_id="BILLING",
            timestamp=now,
            is_staff=False,
            confidence=0.9,
            metadata=json.dumps({}),
        ))

        # Exit from billing zone (no purchase)
        db.add(EventDB(
            event_id="billing-exit-1",
            store_id=store_id,
            camera_id="CAM_BILLING",
            visitor_id=visitor_id,
            event_type="ZONE_EXIT",
            zone_id="BILLING",
            timestamp=now + timedelta(minutes=3),
            dwell_ms=180000,
            is_staff=False,
            confidence=0.9,
            metadata=json.dumps({"abandoned": True}),
        ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        # Should have abandonment_rate > 0
        assert metrics.abandonment_rate > 0, "Visitor who left billing without purchase should count as abandon"

    def test_multiple_abandonments_calculated_correctly(self, db: Session):
        """
        Scenario: 10 visitors enter billing; 3 purchase, 7 abandon.
        Expected: abandonment_rate ≈ 70%.
        """
        now = datetime.utcnow()
        store_id = "STORE_ABANDON_RATE"

        # 10 visitors enter billing
        for i in range(10):
            db.add(EventDB(
                event_id=f"billing-enter-{i}",
                store_id=store_id,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_{i}",
                event_type="ZONE_ENTER",
                zone_id="BILLING",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))

        # 3 purchase
        for i in range(3):
            db.add(POSTransactionDB(
                transaction_id=f"TXN_{i}",
                store_id=store_id,
                timestamp=now + timedelta(minutes=2),
                amount_inr=500.0,
                metadata=json.dumps({"visitor_id": f"VIS_{i}"}),
            ))

        # 7 abandon (exit without purchase)
        for i in range(3, 10):
            db.add(EventDB(
                event_id=f"billing-exit-{i}",
                store_id=store_id,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_{i}",
                event_type="ZONE_EXIT",
                zone_id="BILLING",
                timestamp=now + timedelta(minutes=3),
                dwell_ms=180000,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        # Abandonment rate should be approximately 70% (7 abandoned out of 10)
        expected_rate = 70.0
        actual_rate = metrics.abandonment_rate
        assert 65 <= actual_rate <= 75, f"Expected ~70% abandonment, got {actual_rate}%"


class TestLowConfidenceDetections:
    """Test that low-confidence detections are handled gracefully."""

    def test_low_confidence_detection_still_counted(self, db: Session):
        """
        Scenario: Detection with 0.55 confidence (below typical threshold but flagged).
        Expected: Still counted in metrics with confidence flag.
        """
        now = datetime.utcnow()
        store_id = "STORE_LOW_CONF"

        db.add(EventDB(
            event_id="low-conf-entry",
            store_id=store_id,
            camera_id="CAM_ENTRY",
            visitor_id="VIS_LOW_CONF",
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.55,  # Below typical 0.7 threshold
            metadata=json.dumps({"low_confidence": True}),
        ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        assert metrics.unique_visitors == 1, "Low-confidence detections should not be suppressed"

    def test_very_high_confidence_also_counted(self, db: Session):
        """
        Scenario: Mix of high-confidence (0.95) and medium-confidence (0.75).
        Expected: Both counted, but confidence distribution observable in metadata.
        """
        now = datetime.utcnow()
        store_id = "STORE_CONF_MIX"

        confidences = [0.95, 0.85, 0.75, 0.65]
        for i, conf in enumerate(confidences):
            db.add(EventDB(
                event_id=f"entry-{i}",
                store_id=store_id,
                camera_id="CAM_ENTRY",
                visitor_id=f"VIS_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=conf,
                metadata=json.dumps({}),
            ))

        db.commit()

        metrics = compute_metrics(store_id, db, hours=24, now=now + timedelta(hours=1))
        assert metrics.unique_visitors == 4, "All detections (regardless of confidence) should be counted"


class TestOutputVariation:
    """Ensure outputs are data-driven, not hardcoded."""

    def test_metrics_vary_with_event_count(self, db: Session):
        """
        Scenario: Add different numbers of events and verify metrics change accordingly.
        Expected: Metrics should scale linearly with input.
        This prevents hardcoded output detection.
        """
        now = datetime.utcnow()
        store_id = "STORE_VARY_001"

        # Get baseline metrics (empty store)
        metrics_0 = compute_metrics(store_id, db, hours=24, now=now)
        baseline_visitors = metrics_0.unique_visitors

        # Add 5 visitors
        for i in range(5):
            db.add(EventDB(
                event_id=f"entry-{i}",
                store_id=store_id,
                camera_id="CAM_ENTRY",
                visitor_id=f"VIS_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        metrics_5 = compute_metrics(store_id, db, hours=24, now=now)
        assert metrics_5.unique_visitors == baseline_visitors + 5, "Metrics should scale with input"

        # Add 10 more visitors
        for i in range(5, 15):
            db.add(EventDB(
                event_id=f"entry-{i}",
                store_id=store_id,
                camera_id="CAM_ENTRY",
                visitor_id=f"VIS_{i}",
                event_type="ENTRY",
                timestamp=now + timedelta(seconds=1),
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        metrics_15 = compute_metrics(store_id, db, hours=24, now=now)
        assert metrics_15.unique_visitors == 15, "Metrics should reflect cumulative events"

    def test_funnel_varies_with_conversion(self, db: Session):
        """
        Scenario: Create funnel with different conversion rates and verify they differ.
        Expected: Different input → different funnel shape.
        """
        now = datetime.utcnow()

        # Scenario A: High conversion (80%)
        store_a = "STORE_HIGH_CONV"
        for i in range(10):
            db.add(EventDB(
                event_id=f"a-entry-{i}",
                store_id=store_a,
                camera_id="CAM_ENTRY",
                visitor_id=f"VIS_A_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            # 8 out of 10 visit zone
            if i < 8:
                db.add(EventDB(
                    event_id=f"a-zone-{i}",
                    store_id=store_a,
                    camera_id="CAM_FLOOR",
                    visitor_id=f"VIS_A_{i}",
                    event_type="ZONE_ENTER",
                    zone_id="SKINCARE",
                    timestamp=now + timedelta(minutes=1),
                    is_staff=False,
                    confidence=0.9,
                    metadata=json.dumps({}),
                ))
                # 8 out of 10 purchase
                if i < 8:
                    db.add(POSTransactionDB(
                        transaction_id=f"TXN_A_{i}",
                        store_id=store_a,
                        timestamp=now + timedelta(minutes=5),
                        amount_inr=500.0,
                        metadata=json.dumps({}),
                    ))

        # Scenario B: Low conversion (20%)
        store_b = "STORE_LOW_CONV"
        for i in range(10):
            db.add(EventDB(
                event_id=f"b-entry-{i}",
                store_id=store_b,
                camera_id="CAM_ENTRY",
                visitor_id=f"VIS_B_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            # 2 out of 10 visit zone
            if i < 2:
                db.add(EventDB(
                    event_id=f"b-zone-{i}",
                    store_id=store_b,
                    camera_id="CAM_FLOOR",
                    visitor_id=f"VIS_B_{i}",
                    event_type="ZONE_ENTER",
                    zone_id="SKINCARE",
                    timestamp=now + timedelta(minutes=1),
                    is_staff=False,
                    confidence=0.9,
                    metadata=json.dumps({}),
                ))
                # 2 out of 10 purchase
                db.add(POSTransactionDB(
                    transaction_id=f"TXN_B_{i}",
                    store_id=store_b,
                    timestamp=now + timedelta(minutes=5),
                    amount_inr=500.0,
                    metadata=json.dumps({}),
                ))

        db.commit()

        funnel_a = compute_funnel(store_a, db, hours=24)
        funnel_b = compute_funnel(store_b, db, hours=24)

        # Funnels should have different shapes
        assert funnel_a.steps[1].count > funnel_b.steps[1].count, \
            "High-conversion store should have more zone visits"
        assert funnel_a.steps[2].count >= funnel_b.steps[2].count, \
            "High-conversion store should have more purchases"
