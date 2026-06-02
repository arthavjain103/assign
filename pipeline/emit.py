"""
Event emission: schema-validated events with correct entry/exit and dwell logic.

Event types emitted:
  ENTRY              — vertical-line crossing inward (left→right)  (entry / floor clips)
  EXIT               — vertical-line crossing outward (right→left) (entry / floor clips)
  REENTRY            — visitor re-detected after previous exit (cross-clip re-ID)
  ZONE_ENTER         — first detection in any zone
  ZONE_DWELL         — every 30-second boundary while in zone
  BILLING_QUEUE_JOIN — ZONE_ENTER when queue_depth > 0
  ZONE_EXIT          — visitor leaves zone
  BILLING_QUEUE_ABANDON — joined queue but no POS transaction within 5 min

Key implementation:
  1. ENTRY/EXIT via centroid crossing VERTICAL line (left/right) — not emitted on every frame
  2. ZONE_DWELL fires on each 30s boundary, not once then every frame
  3. Zone state resets on EXIT so a visitor can re-enter cleanly
  4. dwell_ms carried correctly on all zone events
  5. Virtual line positioned at frame width fraction (default 0.5 = center)
"""

import uuid
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DWELL_INTERVAL_S = 30.0   # emit ZONE_DWELL on each 30-second boundary


class EventEmitter:
    """
    Stateful emitter: one instance per video clip.
    Maintains per-visitor crossing state, zone timers, dwell ticks.
    """

    def __init__(self, store_id: str = "STORE_001", line_ratio: float = 0.5):
        self.store_id = store_id
        self.camera_map = {
            "entry":   "CAM_ENTRY_01",
            "floor":   "CAM_FLOOR_01",
            "billing": "CAM_CHECKOUT_01",
        }
        # Virtual counting line: fraction of frame width (VERTICAL line for entry/exit gates)
        # 0.5 = vertical line at mid-frame (works for center-mounted entry cameras)
        # Line orientation: VERTICAL (x-axis crossing) not horizontal
        self.line_ratio = line_ratio

        # Per-visitor state dicts
        self.zone_enter_time:    Dict[str, float] = {}
        self.last_dwell_tick:    Dict[str, int]   = {}
        self.last_centroid_side: Dict[str, int]   = {}   # -1 above line / +1 below
        self.entered:            set[str]         = set()
        self.session_seq:        Dict[str, int]   = {}
        self.reentry_emitted:    set[str]         = set()   # avoid duplicate REENTRY
        self.zone_exit_emitted:  set[str]         = set()   # avoid duplicate ZONE_EXIT
        self.billing_joins:      Dict[str, float] = {}   # visitor_id → join_timestamp

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _next_seq(self, visitor_id: str) -> int:
        self.session_seq[visitor_id] = self.session_seq.get(visitor_id, 0) + 1
        return self.session_seq[visitor_id]

    def _build(
        self,
        *,
        event_type:      str,
        camera_id:       str,
        zone_id:         Optional[str],
        visitor_id:      str,
        event_timestamp: datetime,
        conf:            float,
        is_staff:        bool,
        staff_conf:      float,
        dwell_ms:        int,
        queue_depth:     Optional[int],
        sku_zone:        Optional[str] = None,
    ) -> dict:
        return {
            "event_id":   str(uuid.uuid4()),
            "store_id":   self.store_id,
            "camera_id":  camera_id,
            "visitor_id": visitor_id,
            "event_type": event_type,
            "timestamp":  event_timestamp.isoformat() + "Z",
            "zone_id":    zone_id,
            "dwell_ms":   dwell_ms,
            "is_staff":   is_staff,
            "confidence": round(min(conf, 0.99), 4),
            "metadata": {
                "queue_depth":   queue_depth,
                "sku_zone":      sku_zone,
                "session_seq":   self._next_seq(visitor_id),
                "detector_conf": round(conf, 4),
                "staff_conf":    round(staff_conf, 4),
            },
        }

    # ── Main emit method ──────────────────────────────────────────────────────
    def emit(
        self,
        track_id:        int,
        visitor_id:      str,
        clip_type:       str,
        frame_idx:       int,
        video_fps:       float,
        event_timestamp: datetime,
        conf:            float,
        is_staff:        bool,
        staff_conf:      float,
        session_info:    dict,
        frame:           Any,                    # np.ndarray
        bbox:            Tuple[int, int, int, int],
        queue_depth:     Optional[int] = None,
        is_reentry:      bool = False,
    ) -> Optional[dict]:
        """
        Emit one event for this detection, or None if no event boundary crossed.
        """
        x, y, w, h = bbox
        cx  = x + w // 2                        # centroid x (horizontal)
        now = event_timestamp.timestamp()

        # ── ENTRY / EXIT camera (virtual-line crossing) ───────────────────────
        if clip_type in ("entry", "floor"):
            # Check for REENTRY event (cross-clip re-ID match)
            if is_reentry and visitor_id not in self.reentry_emitted:
                self.reentry_emitted.add(visitor_id)
                camera_id = self.camera_map[clip_type]
                return self._build(
                    event_type      = "REENTRY",
                    camera_id       = camera_id,
                    zone_id         = None,
                    visitor_id      = visitor_id,
                    event_timestamp = event_timestamp,
                    conf            = conf,
                    is_staff        = is_staff,
                    staff_conf      = staff_conf,
                    dwell_ms        = 0,
                    queue_depth     = None,
                )

            camera_id = self.camera_map[clip_type]
            line_x    = int(frame.shape[1] * self.line_ratio)  # vertical line at frame width fraction
            side      = 1 if cx >= line_x else -1  # right (+1) or left (-1) of vertical line
            prev_side = self.last_centroid_side.get(visitor_id)
            self.last_centroid_side[visitor_id] = side

            if prev_side is None or side == prev_side:
                return None   # no crossing this frame

            # Crossing detected — direction → event type
            # LEFT to RIGHT: +1 (entering store)
            # RIGHT to LEFT: -1 (exiting store)
            if prev_side == -1 and side == 1:
                event_type = "ENTRY"
                self.entered.add(visitor_id)
            else:
                event_type = "EXIT"
                self.reset_zone(visitor_id)
                self.reentry_emitted.discard(visitor_id)  # allow future reenters

            return self._build(
                event_type      = event_type,
                camera_id       = camera_id,
                zone_id         = None,
                visitor_id      = visitor_id,
                event_timestamp = event_timestamp,
                conf            = conf,
                is_staff        = is_staff,
                staff_conf      = staff_conf,
                dwell_ms        = 0,
                queue_depth     = None,
            )

        # ── BILLING zone ──────────────────────────────────────────────────────
        if clip_type == "billing":
            camera_id = self.camera_map["billing"]
            zone_id   = "BILLING"

            if visitor_id not in self.zone_enter_time:
                # First appearance in billing zone
                self.zone_enter_time[visitor_id]  = now
                self.last_dwell_tick[visitor_id]  = 0
                event_type = (
                    "BILLING_QUEUE_JOIN"
                    if (queue_depth is not None and queue_depth > 0)
                    else "ZONE_ENTER"
                )
                # Track queue joins for abandon detection
                if event_type == "BILLING_QUEUE_JOIN":
                    self.billing_joins[visitor_id] = now
                
                return self._build(
                    event_type      = event_type,
                    camera_id       = camera_id,
                    zone_id         = zone_id,
                    visitor_id      = visitor_id,
                    event_timestamp = event_timestamp,
                    conf            = conf,
                    is_staff        = is_staff,
                    staff_conf      = staff_conf,
                    dwell_ms        = 0,
                    queue_depth     = queue_depth,
                )

            # Already in zone — emit ZONE_DWELL on each new 30s boundary
            elapsed = now - self.zone_enter_time[visitor_id]
            tick    = int(elapsed // DWELL_INTERVAL_S)
            if tick > self.last_dwell_tick.get(visitor_id, 0):
                self.last_dwell_tick[visitor_id] = tick
                return self._build(
                    event_type      = "ZONE_DWELL",
                    camera_id       = camera_id,
                    zone_id         = zone_id,
                    visitor_id      = visitor_id,
                    event_timestamp = event_timestamp,
                    conf            = conf,
                    is_staff        = is_staff,
                    staff_conf      = staff_conf,
                    dwell_ms        = int(elapsed * 1000),
                    queue_depth     = queue_depth,
                )
            return None   # within current 30s window

        # ── Generic fallback (main floor zone enter) ──────────────────────────
        camera_id = self.camera_map.get(clip_type, "CAM_GENERIC")
        if visitor_id not in self.zone_enter_time:
            self.zone_enter_time[visitor_id] = now
            self.last_dwell_tick[visitor_id] = 0
            return self._build(
                event_type      = "ZONE_ENTER",
                camera_id       = camera_id,
                zone_id         = "GENERAL",
                visitor_id      = visitor_id,
                event_timestamp = event_timestamp,
                conf            = conf,
                is_staff        = is_staff,
                staff_conf      = staff_conf,
                dwell_ms        = 0,
                queue_depth     = queue_depth,
            )
        return None

    def reset_zone(self, visitor_id: str) -> None:
        """Reset zone state on EXIT — visitor can re-enter cleanly."""
        self.zone_enter_time.pop(visitor_id, None)
        self.last_dwell_tick.pop(visitor_id, None)

    def emit_zone_exit(
        self,
        visitor_id: str,
        event_timestamp: datetime,
    ) -> Optional[dict]:
        """
        Emit ZONE_EXIT event when visitor leaves billing zone.
        Called when visitor is no longer detected for >60s.
        """
        if visitor_id in self.zone_exit_emitted:
            return None  # already emitted
        
        if visitor_id not in self.zone_enter_time:
            return None  # never entered
        
        self.zone_exit_emitted.add(visitor_id)
        now = event_timestamp.timestamp()
        elapsed = now - self.zone_enter_time[visitor_id]
        
        camera_id = self.camera_map["billing"]
        return self._build(
            event_type      = "ZONE_EXIT",
            camera_id       = camera_id,
            zone_id         = "BILLING",
            visitor_id      = visitor_id,
            event_timestamp = event_timestamp,
            conf            = 0.99,
            is_staff        = False,
            staff_conf      = 0.0,
            dwell_ms        = int(elapsed * 1000),
            queue_depth     = None,
        )

    def check_queue_abandons(
        self,
        current_visitors: set[str],
        event_timestamp: datetime,
        pos_conversions: Dict[str, float],  # visitor_id → conversion_timestamp
    ) -> list[dict]:
        """
        Detect BILLING_QUEUE_ABANDON: visitor joined queue but didn't convert.
        
        Args:
            current_visitors: set of visitor IDs currently in frame
            event_timestamp: current timestamp
            pos_conversions: dict of visitor_id→timestamp for completed transactions
            
        Returns:
            list of BILLING_QUEUE_ABANDON events
        """
        abandon_events = []
        now = event_timestamp.timestamp()
        
        for visitor_id, join_time in list(self.billing_joins.items()):
            # Skip if still in zone
            if visitor_id in current_visitors:
                continue
            
            # Check if already converted
            if visitor_id in pos_conversions:
                txn_time = pos_conversions[visitor_id]
                if txn_time - join_time >= 0 and txn_time - join_time <= 300:  # 5 min
                    # Converted within window
                    del self.billing_joins[visitor_id]
                    continue
            
            # Check if > 5 min passed since join
            time_in_queue = now - join_time
            if time_in_queue > 300:  # 5 minutes
                abandon_events.append(
                    self._build(
                        event_type      = "BILLING_QUEUE_ABANDON",
                        camera_id       = self.camera_map["billing"],
                        zone_id         = "BILLING",
                        visitor_id      = visitor_id,
                        event_timestamp = event_timestamp,
                        conf            = 0.99,
                        is_staff        = False,
                        staff_conf      = 0.0,
                        dwell_ms        = int(time_in_queue * 1000),
                        queue_depth     = None,
                    )
                )
                del self.billing_joins[visitor_id]
        
        return abandon_events
