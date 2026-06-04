import uuid
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

DWELL_INTERVAL_S = 30.0   # emit ZONE_DWELL on each 30-second boundary

# ── Hysteresis margin around the virtual counting line (pixels) ──────────────
# Centroids within [line_y - HYSTERESIS_PX, line_y + HYSTERESIS_PX] are
# treated as "dead-zone" (side = 0) — no event emitted.
HYSTERESIS_PX = 40


class EventEmitter:

    def __init__(self, store_id: str = "STORE_001", line_ratio: float = 0.5):
        self.store_id = store_id
        self.camera_map = {
            "entry":   "CAM_ENTRY_01",
            "floor":   "CAM_FLOOR_01",
            "billing": "CAM_CHECKOUT_01",
        }
        # Virtual counting line: fraction of frame height
        self.line_ratio = line_ratio

        # Per-visitor state dicts
        self.zone_enter_time:    Dict[str, float] = {}
        self.last_dwell_tick:    Dict[str, int]   = {}
        self.entered:            set[str]         = set()
        self.session_seq:        Dict[str, int]   = {}
        self.reentry_emitted:    set[str]         = set()
        self.zone_exit_emitted:  set[str]         = set()
        self.billing_joins:      Dict[str, float] = {}

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
        frame:           Any,
        bbox:            Tuple[int, int, int, int],
        queue_depth:     Optional[int] = None,
        is_reentry:      bool = False,
        crossing_event:  Optional[str] = None,
    ) -> Optional[dict]:

        x, y, w, h = bbox
        cy  = y + h // 2
        now = event_timestamp.timestamp()

        # ── ENTRY / EXIT camera (NEW LineTracker logic) ───────────
        if clip_type in ("entry", "floor"):
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
            
            # Use crossing_event from LineTracker (computed at frame level in detect.py)
            event_type = crossing_event
            if event_type is None:
                return None
            
            # Update state based on crossing type
            if event_type == "ENTRY":
                self.entered.add(visitor_id)
            elif event_type == "EXIT":
                self.reset_zone(visitor_id)
                self.reentry_emitted.discard(visitor_id)

            camera_id = self.camera_map[clip_type]
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

        # ── BILLING zone (NEW line crossing logic) ───────────────────────────
        if clip_type == "billing":
            camera_id = self.camera_map["billing"]
            zone_id   = "BILLING"
            
            # Use line crossing event to track queue join (only once per crossing)
            if crossing_event == "ENTRY":
                # Customer entered billing zone - emit BILLING_QUEUE_JOIN
                self.zone_enter_time[visitor_id]  = now
                self.last_dwell_tick[visitor_id]  = 0
                self.billing_joins[visitor_id] = now
                
                return self._build(
                    event_type      = "BILLING_QUEUE_JOIN",
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
            elif crossing_event == "EXIT":
                # Customer exited billing zone
                self.reset_zone(visitor_id)
                return None

            # For frames without crossing event, check for ZONE_DWELL
            if visitor_id not in self.zone_enter_time:
                return None

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
            return None

        # ── Generic fallback ──────────────────────────────────────────────────
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
        self.zone_enter_time.pop(visitor_id, None)
        self.last_dwell_tick.pop(visitor_id, None)
        # FIX (Bug 1): clear zone_exit_emitted so a re-entering visitor can
        # receive a fresh ZONE_EXIT on a subsequent billing visit.
        self.zone_exit_emitted.discard(visitor_id)

    def emit_zone_exit(
        self,
        visitor_id: str,
        event_timestamp: datetime,
    ) -> Optional[dict]:

        if visitor_id in self.zone_exit_emitted:
            return None

        if visitor_id not in self.zone_enter_time:
            return None

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
        pos_conversions: Dict[str, float],
    ) -> list[dict]:

        abandon_events = []
        now = event_timestamp.timestamp()

        for visitor_id, join_time in list(self.billing_joins.items()):
            if visitor_id in current_visitors:
                continue

            if visitor_id in pos_conversions:
                txn_time = pos_conversions[visitor_id]
                if 0 <= txn_time - join_time <= 300:
                    del self.billing_joins[visitor_id]
                    continue

            time_in_queue = now - join_time
            if time_in_queue > 300:
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