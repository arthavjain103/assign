"""
Pydantic v2 models for Store Intelligence events and domain entities.
All models implement strict validation with clear error messages.
"""
from datetime import datetime
from typing import Optional, Any
from enum import Enum
from uuid import UUID
import uuid

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    """Valid event types emitted by the detection pipeline."""
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class Event(BaseModel):
    """
    Core event schema for Store Intelligence.
    Matches the acceptance-gate format exactly.
    All timestamps are ISO-8601 UTC.
    """
    event_id: str = Field(
        ...,
        description="UUID v4 unique globally; prevents duplicates on replay",
    )
    store_id: str = Field(
        ..., 
        description="E.g., 'STORE_BLR_002'; correlates with POS transactions"
    )
    camera_id: str = Field(
        ..., 
        description="E.g., 'CAM_ENTRY_01'; determines zone_id eligibility"
    )
    visitor_id: str = Field(
        ..., 
        description="PER-SESSION identifier; resets on EXIT+REENTRY"
    )
    event_type: EventType = Field(..., description="ENTRY, EXIT, ZONE_DWELL, etc.")
    timestamp: str = Field(
        ..., 
        description="ISO-8601 UTC; derived as clip_start + frame/fps"
    )
    zone_id: Optional[str] = Field(
        default=None,
        description="null for ENTRY/EXIT; e.g. 'SKINCARE' for ZONE_* events"
    )
    dwell_ms: int = Field(
        default=0, 
        description="Milliseconds; 0 for instantaneous, >0 for continued dwell"
    )
    is_staff: bool = Field(
        default=False, 
        description="If true, exclude from customer metrics"
    )
    confidence: float = Field(
        default=0.5, 
        ge=0.0, 
        le=1.0, 
        description="Real detection confidence (0–1); never suppress low values"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="queue_depth, sku_zone, session_seq, etc."
    )

    model_config = {"str_strip_whitespace": True}

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """Ensure timestamp is valid ISO-8601 UTC format."""
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"timestamp must be ISO-8601 UTC; got {v}")
        return v

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        """Ensure event_id is a valid UUID."""
        try:
            UUID(v)
        except ValueError:
            raise ValueError(f"event_id must be valid UUID v4; got {v}")
        return v


class EventIngestionRequest(BaseModel):
    """Batch ingest request: ≤500 events."""
    events: list[Event] = Field(..., min_items=1, max_items=500)

    model_config = {"str_strip_whitespace": True}


class EventIngestionResponse(BaseModel):
    """Per-event status on ingest."""
    class EventStatus(BaseModel):
        event_id: str
        status: str  # "accepted" | "duplicate" | "rejected"
        message: str = ""

    total: int
    accepted: int
    duplicates: int
    rejected: int
    events: list[EventStatus]


class MetricsResponse(BaseModel):
    """Live store metrics; real-time, never cached."""
    store_id: str
    timestamp: str
    unique_visitors: int
    conversion_rate: float  # converted / total_visitors
    avg_dwell_per_zone: dict[str, float]  # zone_id -> avg dwell_ms
    current_queue_depth: int
    abandonment_rate: float  # abandoners / billing_zone_visitors
    avg_basket_value_inr: float
    total_revenue_inr: float
    
    # Observability: Data quality metrics
    avg_detection_confidence: float = Field(
        default=0.0, 
        description="Average YOLO confidence across all detections (0–1)",
        ge=0.0, 
        le=1.0
    )
    low_confidence_ratio: float = Field(
        default=0.0,
        description="Fraction of detections with confidence < 0.7 (0–1); indicates data quality",
        ge=0.0,
        le=1.0
    )
    data_quality_score: float = Field(
        default=1.0,
        description="Composite quality score (0–1); 1.0 = all high-conf, 0.0 = all low-conf",
        ge=0.0,
        le=1.0
    )
    event_count_24h: int = Field(
        default=0,
        description="Total events (all types) in last 24h; proxy for traffic volume"
    )


class FunnelStep(BaseModel):
    """Single step in the conversion funnel."""
    step: str  # "ENTRY", "ZONE_VISIT", "BILLING_QUEUE", "PURCHASE"
    count: int
    drop_off_percent: float = 0.0  # drop vs previous step


class FunnelResponse(BaseModel):
    """Conversion funnel: entry → zones → billing → purchase."""
    store_id: str
    timestamp: str
    steps: list[FunnelStep]
    unique_sessions: int


class HeatmapZone(BaseModel):
    """Heatmap data for a single zone."""
    zone_id: str
    visit_count: int
    avg_dwell_ms: float
    intensity: float  # 0–100 normalized


class HeatmapResponse(BaseModel):
    """Heatmap: zone visit frequency + dwell intensity."""
    store_id: str
    timestamp: str
    zones: list[HeatmapZone]
    data_confidence: bool  # False if <20 sessions in window


class Anomaly(BaseModel):
    """Single anomaly alert."""
    anomaly_type: str  # "QUEUE_SPIKE", "CONVERSION_DROP", "DEAD_ZONE"
    severity: str  # "INFO", "WARN", "CRITICAL"
    message: str
    suggested_action: str


class AnomaliesResponse(BaseModel):
    """Active anomalies: queue spike, conversion drop, dead zones."""
    store_id: str
    timestamp: str
    anomalies: list[Anomaly]


class HealthResponse(BaseModel):
    """Service health: status, last event per store, staleness warnings."""
    status: str  # "healthy" | "degraded" | "unhealthy"
    timestamp: str
    stores: dict[str, dict[str, Any]]  # store_id -> {last_event_ts, lag_ms, stale}


class POSTransaction(BaseModel):
    """POS transaction for conversion correlation."""
    store_id: str
    transaction_id: str
    timestamp: str  # ISO-8601 UTC
    basket_value_inr: float


class StoreLayout(BaseModel):
    """Store layout: zones, cameras, open hours."""
    store_id: str
    zones: dict[str, dict[str, Any]]  # zone_id -> {camera_ids, polygon}
    open_hours: dict[str, tuple[str, str]]  # "mon" -> ("08:00", "22:00")
    cameras: dict[str, dict[str, Any]]  # camera_id -> {location, coverage}
