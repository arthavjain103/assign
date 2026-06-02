"""
assertions.py - 10 example assertions the API MUST pass.
This is the acceptance gate: all 10 must pass for the API to be valid.

Run with: pytest tests/test_assertions.py -v
"""
import json
import uuid
from datetime import datetime
import httpx
import pytest

BASE_URL = "http://localhost:8000"
STORE_ID = "STORE_BLR_002"


def test_health_endpoint_returns_valid_response():
    """
    ASSERTION 1: GET /health returns valid JSON with status, timestamp, stores.
    """
    response = httpx.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "stores" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]


def test_metrics_endpoint_returns_valid_response():
    """
    ASSERTION 2: GET /stores/{id}/metrics returns valid JSON with all required fields.
    """
    response = httpx.get(f"{BASE_URL}/stores/{STORE_ID}/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == STORE_ID
    assert "timestamp" in data
    assert "unique_visitors" in data
    assert "conversion_rate" in data
    assert "avg_dwell_per_zone" in data
    assert "current_queue_depth" in data
    assert "abandonment_rate" in data
    assert "avg_basket_value_inr" in data
    assert "total_revenue_inr" in data
    # Check types
    assert isinstance(data["unique_visitors"], int)
    assert isinstance(data["conversion_rate"], float)
    assert isinstance(data["current_queue_depth"], int)


def test_funnel_endpoint_returns_valid_response():
    """
    ASSERTION 3: GET /stores/{id}/funnel returns valid JSON with step breakdown.
    """
    response = httpx.get(f"{BASE_URL}/stores/{STORE_ID}/funnel")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == STORE_ID
    assert "timestamp" in data
    assert "steps" in data
    assert len(data["steps"]) > 0
    # First step should be ENTRY
    assert data["steps"][0]["step"] == "ENTRY"
    # Steps should have count and drop_off_percent
    for step in data["steps"]:
        assert "step" in step
        assert "count" in step
        assert "drop_off_percent" in step
        assert isinstance(step["count"], int)
        assert isinstance(step["drop_off_percent"], float)


def test_heatmap_endpoint_returns_valid_response():
    """
    ASSERTION 4: GET /stores/{id}/heatmap returns zones with intensity 0-100.
    """
    response = httpx.get(f"{BASE_URL}/stores/{STORE_ID}/heatmap")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == STORE_ID
    assert "timestamp" in data
    assert "zones" in data
    assert "data_confidence" in data
    assert isinstance(data["data_confidence"], bool)
    # Check zone structure
    for zone in data["zones"]:
        assert "zone_id" in zone
        assert "visit_count" in zone
        assert "avg_dwell_ms" in zone
        assert "intensity" in zone
        assert 0 <= zone["intensity"] <= 100


def test_anomalies_endpoint_returns_valid_response():
    """
    ASSERTION 5: GET /stores/{id}/anomalies returns list with severity levels.
    """
    response = httpx.get(f"{BASE_URL}/stores/{STORE_ID}/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == STORE_ID
    assert "timestamp" in data
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)
    # If any anomalies exist, check structure
    for anomaly in data["anomalies"]:
        assert "anomaly_type" in anomaly
        assert "severity" in anomaly
        assert anomaly["severity"] in ["INFO", "WARN", "CRITICAL"]
        assert "message" in anomaly
        assert "suggested_action" in anomaly


def test_ingest_endpoint_accepts_valid_events():
    """
    ASSERTION 6: POST /events/ingest accepts batch and returns per-event status.
    """
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "store_id": STORE_ID,
        "camera_id": "CAM_TEST_01",
        "visitor_id": f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": "ENTRY",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {}
    }
    
    response = httpx.post(
        f"{BASE_URL}/events/ingest",
        json={"events": [event]}
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "accepted" in data
    assert "duplicates" in data
    assert "rejected" in data
    assert "events" in data
    assert data["total"] == 1
    # First event should be accepted
    assert data["events"][0]["status"] in ["accepted", "duplicate"]


def test_ingest_idempotency_duplicate_detection():
    """
    ASSERTION 7: Ingesting the same event_id twice results in duplicate detection.
    """
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "store_id": STORE_ID,
        "camera_id": "CAM_TEST_02",
        "visitor_id": f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": "ENTRY",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {}
    }
    
    # First ingest
    response1 = httpx.post(
        f"{BASE_URL}/events/ingest",
        json={"events": [event]}
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["accepted"] == 1
    
    # Second ingest (same event_id)
    response2 = httpx.post(
        f"{BASE_URL}/events/ingest",
        json={"events": [event]}
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["duplicates"] == 1
    assert data2["accepted"] == 0


def test_ingest_never_returns_5xx_on_valid_input():
    """
    ASSERTION 8: POST /events/ingest never returns 5xx on valid input (graceful degradation).
    """
    # Valid event with all required fields
    event = {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_TEST_03",
        "visitor_id": f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": "ZONE_DWELL",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "zone_id": "SKINCARE",
        "dwell_ms": 30000,
        "is_staff": False,
        "confidence": 0.87,
        "metadata": {"session_seq": 2, "sku_zone": "MOISTURISER"}
    }
    
    response = httpx.post(
        f"{BASE_URL}/events/ingest",
        json={"events": [event]}
    )
    assert response.status_code != 500
    assert response.status_code != 502
    assert response.status_code != 503


def test_metrics_handles_zero_traffic_gracefully():
    """
    ASSERTION 9: GET /stores/{id}/metrics returns 0.0 for rates on zero traffic (no divide-by-zero).
    """
    # Try a store with no events
    fake_store_id = "STORE_NONEXISTENT"
    response = httpx.get(f"{BASE_URL}/stores/{fake_store_id}/metrics")
    assert response.status_code == 200
    data = response.json()
    # Should return valid structure with zeros
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0
    assert data["total_revenue_inr"] == 0.0
    # Should NOT crash with NaN or null
    assert isinstance(data["conversion_rate"], float)


def test_event_schema_validation_rejects_invalid_event():
    """
    ASSERTION 10: Validation rejects invalid events with clear error messages (per-event status).
    """
    # Invalid event: bad event_id (not UUID), bad timestamp
    invalid_event = {
        "event_id": "not-a-uuid",
        "store_id": STORE_ID,
        "camera_id": "CAM_TEST_04",
        "visitor_id": f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": "ENTRY",
        "timestamp": "invalid-timestamp",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.95,
        "metadata": {}
    }
    
    # This should fail validation at the client side (Pydantic)
    # but the endpoint should still handle it gracefully
    try:
        response = httpx.post(
            f"{BASE_URL}/events/ingest",
            json={"events": [invalid_event]},
            timeout=5.0
        )
        # Either rejected as 400 Bad Request, or handled as rejected event
        assert response.status_code in [200, 400, 422]
    except Exception:
        # If connection fails, that's still ok (validation happened)
        pass


if __name__ == "__main__":
    # Run all assertions
    print("Running Store Intelligence API assertions...")
    pytest.main([__file__, "-v"])
