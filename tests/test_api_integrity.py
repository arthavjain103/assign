"""
API Integrity Tests - Verify responses are data-driven, not hardcoded.

This test suite ensures:
1. Outputs vary with input (no hardcoded responses)
2. Metrics scale linearly with event count
3. Different stores get different metrics
4. Funnel shapes vary with conversion behavior

Run with: pytest tests/test_api_integrity.py -v
"""

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db import EventDB, POSTransactionDB, engine, SessionLocal, init_db
from app.metrics import compute_metrics
from app.funnel import compute_funnel
from app.heatmap import compute_heatmap
from app.anomalies import compute_anomalies


import pytest


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


class TestAPIDataDriven:
    """Verify API responses vary with input data."""

    def test_empty_store_has_zero_metrics(self, db: Session):
        """
        Baseline: Empty store should have all-zero metrics.
        This proves the API is computing, not returning hardcoded values.
        """
        now = datetime.utcnow()
        store_id = "STORE_BASELINE_EMPTY"

        metrics = compute_metrics(store_id, db, hours=24, now=now)

        # All zeros
        assert metrics.unique_visitors == 0
        assert metrics.conversion_rate == 0.0
        assert metrics.abandonment_rate == 0.0
        assert metrics.current_queue_depth == 0
        assert metrics.avg_basket_value_inr == 0.0
        assert metrics.total_revenue_inr == 0.0
        assert metrics.event_count_24h == 0

    def test_metrics_scale_with_visitor_count(self, db: Session):
        """
        Test 1: Add 10 visitors → unique_visitors = 10
        Test 2: Add 20 more visitors → unique_visitors = 30
        
        This proves metrics are NOT hardcoded.
        """
        now = datetime.utcnow()
        store_id = "STORE_SCALE_TEST"

        # Baseline
        baseline = compute_metrics(store_id, db, hours=24, now=now)
        assert baseline.unique_visitors == 0

        # Add 10 visitors
        for i in range(10):
            db.add(EventDB(
                event_id=f"v1-{i}",
                store_id=store_id,
                camera_id="CAM_1",
                visitor_id=f"VIS_BATCH1_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        metrics_10 = compute_metrics(store_id, db, hours=24, now=now)
        assert metrics_10.unique_visitors == 10, "Should have 10 visitors"

        # Add 20 more
        for i in range(20):
            db.add(EventDB(
                event_id=f"v2-{i}",
                store_id=store_id,
                camera_id="CAM_1",
                visitor_id=f"VIS_BATCH2_{i}",
                event_type="ENTRY",
                timestamp=now + timedelta(hours=1),
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        metrics_30 = compute_metrics(store_id, db, hours=24, now=now)
        assert metrics_30.unique_visitors == 30, "Should have 30 visitors total"

        # Verify linear scaling
        assert metrics_30.unique_visitors == metrics_10.unique_visitors + 20

    def test_conversion_rate_varies_with_purchases(self, db: Session):
        """
        Scenario 1: 10 entries, 2 purchases → 20% conversion
        Scenario 2: 10 entries, 5 purchases → 50% conversion
        Scenario 3: 10 entries, 0 purchases → 0% conversion
        
        Different rates prove computation is real.
        """
        now = datetime.utcnow()

        # Scenario 1: 20% conversion
        store_1 = "STORE_CONV_20"
        for i in range(10):
            db.add(EventDB(
                event_id=f"s1-entry-{i}",
                store_id=store_1,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_S1_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            # 2 purchases
            if i < 2:
                db.add(POSTransactionDB(
                    transaction_id=f"txn_s1_{i}",
                    store_id=store_1,
                    timestamp=now + timedelta(minutes=2),
                    basket_value_inr=500.0,
                    metadata=json.dumps({}),
                ))
        db.commit()

        rate_1 = compute_metrics(store_1, db, hours=24, now=now)
        assert rate_1.conversion_rate == 0.2, "Expected 20% conversion"

        # Scenario 2: 50% conversion
        store_2 = "STORE_CONV_50"
        for i in range(10):
            db.add(EventDB(
                event_id=f"s2-entry-{i}",
                store_id=store_2,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_S2_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            # 5 purchases
            if i < 5:
                db.add(POSTransactionDB(
                    transaction_id=f"txn_s2_{i}",
                    store_id=store_2,
                    timestamp=now + timedelta(minutes=2),
                    basket_value_inr=500.0,
                    metadata=json.dumps({}),
                ))
        db.commit()

        rate_2 = compute_metrics(store_2, db, hours=24, now=now)
        assert rate_2.conversion_rate == 0.5, "Expected 50% conversion"

        # Scenario 3: 0% conversion
        store_3 = "STORE_CONV_0"
        for i in range(10):
            db.add(EventDB(
                event_id=f"s3-entry-{i}",
                store_id=store_3,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_S3_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        rate_3 = compute_metrics(store_3, db, hours=24, now=now)
        assert rate_3.conversion_rate == 0.0, "Expected 0% conversion"

        # Verify all three are different
        assert rate_1.conversion_rate != rate_2.conversion_rate
        assert rate_2.conversion_rate != rate_3.conversion_rate
        assert rate_1.conversion_rate != rate_3.conversion_rate

    def test_queue_depth_varies_with_occupancy(self, db: Session):
        """
        Queue depth should vary based on current occupancy in billing zone.
        Test different concurrent customer counts.
        """
        now = datetime.utcnow()
        store_id = "STORE_QUEUE_VAR"

        # Scenario 1: 3 concurrent customers in billing
        for i in range(3):
            db.add(EventDB(
                event_id=f"q1-{i}",
                store_id=store_id,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_Q1_{i}",
                event_type="ZONE_ENTER",
                zone_id="BILLING",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        queue_3 = compute_metrics(store_id, db, hours=24, now=now)
        assert queue_3.current_queue_depth == 3

        # Scenario 2: Add 5 more (total 8)
        for i in range(3, 8):
            db.add(EventDB(
                event_id=f"q2-{i}",
                store_id=store_id,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_Q2_{i}",
                event_type="ZONE_ENTER",
                zone_id="BILLING",
                timestamp=now + timedelta(seconds=1),
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        queue_8 = compute_metrics(store_id, db, hours=24, now=now)
        assert queue_8.current_queue_depth == 8, "Expected 8 in queue"

        # Verify increase
        assert queue_8.current_queue_depth > queue_3.current_queue_depth

    def test_abandonment_rate_varies(self, db: Session):
        """
        Different stores with different abandonment rates should have
        measurably different abandonment_rate values.
        """
        now = datetime.utcnow()

        # Store A: Low abandonment (7 out of 10 convert)
        store_a = "STORE_ABANDON_LOW"
        for i in range(10):
            db.add(EventDB(
                event_id=f"a-billing-{i}",
                store_id=store_a,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_A_{i}",
                event_type="ZONE_ENTER",
                zone_id="BILLING",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            if i < 7:  # 70% convert
                db.add(POSTransactionDB(
                    transaction_id=f"txn_a_{i}",
                    store_id=store_a,
                    timestamp=now + timedelta(minutes=2),
                    basket_value_inr=500.0,
                    metadata=json.dumps({}),
                ))
        db.commit()

        abandon_a = compute_metrics(store_a, db, hours=24, now=now)
        assert abandon_a.abandonment_rate == 0.3, "Expected 30% abandonment"

        # Store B: High abandonment (2 out of 10 convert)
        store_b = "STORE_ABANDON_HIGH"
        for i in range(10):
            db.add(EventDB(
                event_id=f"b-billing-{i}",
                store_id=store_b,
                camera_id="CAM_BILLING",
                visitor_id=f"VIS_B_{i}",
                event_type="ZONE_ENTER",
                zone_id="BILLING",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            if i < 2:  # 20% convert
                db.add(POSTransactionDB(
                    transaction_id=f"txn_b_{i}",
                    store_id=store_b,
                    timestamp=now + timedelta(minutes=2),
                    basket_value_inr=500.0,
                    metadata=json.dumps({}),
                ))
        db.commit()

        abandon_b = compute_metrics(store_b, db, hours=24, now=now)
        assert abandon_b.abandonment_rate == 0.8, "Expected 80% abandonment"

        # Verify they differ
        assert abandon_a.abandonment_rate != abandon_b.abandonment_rate

    def test_data_quality_varies_with_confidence(self, db: Session):
        """
        Stores with all high-confidence detections should have
        higher data_quality_score than stores with low-confidence detections.
        """
        now = datetime.utcnow()

        # Store High-Conf: All detections are 0.95 confidence
        store_high = "STORE_DATA_QUALITY_HIGH"
        for i in range(10):
            db.add(EventDB(
                event_id=f"high-{i}",
                store_id=store_high,
                camera_id="CAM_1",
                visitor_id=f"VIS_HIGH_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.95,
                metadata=json.dumps({}),
            ))
        db.commit()

        quality_high = compute_metrics(store_high, db, hours=24, now=now)

        # Store Low-Conf: All detections are 0.55 confidence
        store_low = "STORE_DATA_QUALITY_LOW"
        for i in range(10):
            db.add(EventDB(
                event_id=f"low-{i}",
                store_id=store_low,
                camera_id="CAM_1",
                visitor_id=f"VIS_LOW_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.55,
                metadata=json.dumps({}),
            ))
        db.commit()

        quality_low = compute_metrics(store_low, db, hours=24, now=now)

        # High-confidence store should have higher quality score
        assert quality_high.data_quality_score > quality_low.data_quality_score
        assert quality_high.avg_detection_confidence > quality_low.avg_detection_confidence

    def test_funnel_varies_across_stores(self, db: Session):
        """
        Different stores with different conversion funnels should
        have measurably different funnel shapes.
        """
        now = datetime.utcnow()

        # Store with high funnel completion (80% → 75% → 70% → 50%)
        store_good = "STORE_FUNNEL_GOOD"
        entries = 100
        for i in range(entries):
            db.add(EventDB(
                event_id=f"good-entry-{i}",
                store_id=store_good,
                camera_id="CAM_1",
                visitor_id=f"VIS_GOOD_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            # 80% visit zone
            if i < 80:
                db.add(EventDB(
                    event_id=f"good-zone-{i}",
                    store_id=store_good,
                    camera_id="CAM_1",
                    visitor_id=f"VIS_GOOD_{i}",
                    event_type="ZONE_ENTER",
                    zone_id="SKINCARE",
                    timestamp=now + timedelta(minutes=1),
                    is_staff=False,
                    confidence=0.9,
                    metadata=json.dumps({}),
                ))
                # 75% of those go to billing (60 out of 80)
                if i < 60:
                    db.add(EventDB(
                        event_id=f"good-billing-{i}",
                        store_id=store_good,
                        camera_id="CAM_BILLING",
                        visitor_id=f"VIS_GOOD_{i}",
                        event_type="ZONE_ENTER",
                        zone_id="BILLING",
                        timestamp=now + timedelta(minutes=3),
                        is_staff=False,
                        confidence=0.9,
                        metadata=json.dumps({}),
                    ))
                    # 50% purchase (30 out of 60)
                    if i < 30:
                        db.add(POSTransactionDB(
                            transaction_id=f"txn_good_{i}",
                            store_id=store_good,
                            timestamp=now + timedelta(minutes=5),
                            basket_value_inr=500.0,
                            metadata=json.dumps({}),
                        ))
        db.commit()

        funnel_good = compute_funnel(store_good, db, hours=24)

        # Store with poor funnel (only 20% complete)
        store_poor = "STORE_FUNNEL_POOR"
        for i in range(entries):
            db.add(EventDB(
                event_id=f"poor-entry-{i}",
                store_id=store_poor,
                camera_id="CAM_1",
                visitor_id=f"VIS_POOR_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
            # 20% visit zone
            if i < 20:
                db.add(EventDB(
                    event_id=f"poor-zone-{i}",
                    store_id=store_poor,
                    camera_id="CAM_1",
                    visitor_id=f"VIS_POOR_{i}",
                    event_type="ZONE_ENTER",
                    zone_id="SKINCARE",
                    timestamp=now + timedelta(minutes=1),
                    is_staff=False,
                    confidence=0.9,
                    metadata=json.dumps({}),
                ))
                # 20% of those to billing (4 out of 20)
                if i < 4:
                    db.add(EventDB(
                        event_id=f"poor-billing-{i}",
                        store_id=store_poor,
                        camera_id="CAM_BILLING",
                        visitor_id=f"VIS_POOR_{i}",
                        event_type="ZONE_ENTER",
                        zone_id="BILLING",
                        timestamp=now + timedelta(minutes=3),
                        is_staff=False,
                        confidence=0.9,
                        metadata=json.dumps({}),
                    ))
                    # 25% purchase (1 out of 4)
                    if i < 1:
                        db.add(POSTransactionDB(
                            transaction_id=f"txn_poor_{i}",
                            store_id=store_poor,
                            timestamp=now + timedelta(minutes=5),
                            basket_value_inr=500.0,
                            metadata=json.dumps({}),
                        ))
        db.commit()

        funnel_poor = compute_funnel(store_poor, db, hours=24)

        # Compare funnel shapes
        # Good store should have more entries reaching later stages
        assert funnel_good.steps[1].count > funnel_poor.steps[1].count  # Zone visits
        assert funnel_good.steps[2].count >= funnel_poor.steps[2].count  # Billing
        assert funnel_good.steps[3].count >= funnel_poor.steps[3].count  # Purchases

    def test_different_stores_isolated(self, db: Session):
        """
        Metrics for Store A should not include events from Store B.
        """
        now = datetime.utcnow()

        # Store A: 50 visitors
        for i in range(50):
            db.add(EventDB(
                event_id=f"a-{i}",
                store_id="STORE_A",
                camera_id="CAM_A",
                visitor_id=f"VIS_A_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))

        # Store B: 100 visitors
        for i in range(100):
            db.add(EventDB(
                event_id=f"b-{i}",
                store_id="STORE_B",
                camera_id="CAM_B",
                visitor_id=f"VIS_B_{i}",
                event_type="ENTRY",
                timestamp=now,
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))

        db.commit()

        metrics_a = compute_metrics("STORE_A", db, hours=24, now=now)
        metrics_b = compute_metrics("STORE_B", db, hours=24, now=now)

        # Each store should only see its own events
        assert metrics_a.unique_visitors == 50
        assert metrics_b.unique_visitors == 100
        assert metrics_a.event_count_24h == 50
        assert metrics_b.event_count_24h == 100


class TestNoHardcodedValues:
    """Verify that API has no hardcoded values."""

    def test_no_hardcoded_metrics(self, db: Session):
        """
        If API had hardcoded responses, this test would fail:
        adding new data would not change output.
        """
        now = datetime.utcnow()
        store_id = "STORE_NO_HARDCODE"

        # Get baseline (empty)
        baseline = compute_metrics(store_id, db, hours=24, now=now)
        baseline_visitors = baseline.unique_visitors

        # Add 1 visitor
        db.add(EventDB(
            event_id="hardcode-test-1",
            store_id=store_id,
            camera_id="CAM_1",
            visitor_id="VIS_HARDCODE_1",
            event_type="ENTRY",
            timestamp=now,
            is_staff=False,
            confidence=0.9,
            metadata=json.dumps({}),
        ))
        db.commit()

        # Get metrics again
        after_1 = compute_metrics(store_id, db, hours=24, now=now)
        after_1_visitors = after_1.unique_visitors

        # Must change
        assert after_1_visitors != baseline_visitors, \
            "Adding visitor should change unique_visitors count (hardcoded check)"
        assert after_1_visitors == baseline_visitors + 1, \
            "Must increase by exactly 1"

        # Add 5 more
        for i in range(5):
            db.add(EventDB(
                event_id=f"hardcode-test-{i+2}",
                store_id=store_id,
                camera_id="CAM_1",
                visitor_id=f"VIS_HARDCODE_{i+2}",
                event_type="ENTRY",
                timestamp=now + timedelta(seconds=i),
                is_staff=False,
                confidence=0.9,
                metadata=json.dumps({}),
            ))
        db.commit()

        after_6 = compute_metrics(store_id, db, hours=24, now=now)
        assert after_6.unique_visitors == 6, "Should have 6 visitors total"
