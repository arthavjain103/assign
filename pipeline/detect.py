"""
Detection Pipeline: YOLOv8s + Native Ultralytics Tracking (ByteTrack / BoT-SORT)

1. DESIGN PHILOSOPHY & TRACKER SELECTION
   - Priority: Minimize offline-store conversion-rate inflation caused by phantom IDs.
   - Entry / Floor View: ByteTrack (Fast, low-memory, optimized for open-space rapid motion).
   - Billing Counter View: BoT-SORT (Uses appearance embeddings to persist IDs through queue bunching/occlusions).

2. KEY PIPELINE CONFIGURATIONS
   - Downsampling: vid_stride=3 (Skips 2 frames to boost throughput 3x without losing track coherence).
   - Precision & Filtering: half=True (FP16 execution) + classes=[0] (Person-only inference).
   - Confidence Floor: conf=0.25 (Low detections are preserved with metadata flags to avoid info loss).
   - Exception Guards: Bbox clamping and (w > 0, h > 0) checks prevent degenerate crop crashes.

3. RE-ID & TEMPORAL GATING STRATEGY
   - Camera-invariant re-matching uses the last frame's BoT-SORT appearance embedding on exit.
   - Matching Criteria: Cosine Similarity > 0.7 AND Time Delta < 15 minutes -> REENTRY event.
   - If outside these bounds -> Triggers a NEW ENTRY event. Low-confidence merges (0.65–0.70) are flagged.

4. QUEUE DEPTH CALCULATION (Billing Zone Only)
   - Formula: queue_depth = count(distinct visitor_id in BILLING zone) - staff_count
   - Filters out: staff with black uniforms (dark ratio ≥55%) OR pink uniforms (pink ratio ≥50%)
   - Captures raw customer wait metrics for accurate queue analytics

6. OBSERVABILITY & OUTPUT
   - Outputs structured, append-only newline-delimited JSON (events.jsonl).
   - Emits structured execution metrics: frame indices, zone transitions, confidence tracking, and active ID counts.
"""
import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
import sys

import cv2
import numpy as np
from ultralytics import YOLO

# Handle both module and script/notebook execution contexts
try:
    from .tracker import SessionManager, ReIDTracker
    from .emit import EventEmitter
    from .staff_vlm import is_staff_vit, STAFF_ZONE_POLYGON, get_staff_registry
    from .entry_exit_detector import LineTracker
except ImportError:
    # Fallback for script/notebook execution
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tracker import SessionManager, ReIDTracker
    from emit import EventEmitter
    from staff_vlm import is_staff_vit, STAFF_ZONE_POLYGON, get_staff_registry
    from entry_exit_detector import LineTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Clip type to camera ID mapping ──────────────────────────────────────────
CLIP_TYPE_TO_CAMERA = {
    "entry":      "CAM_3",
    "floor":      "CAM_1",  # or CAM_2
    "billing":    "CAM_5",
    "back_office": "CAM_4",
}

TRACKER_CONFIG = {
    "entry":   "bytetrack.yaml",
    "floor":   "bytetrack.yaml",
    "billing": "botsort.yaml",
}

COCO_PERSON_CLASS = 0
DEFAULT_CONF      = 0.25
DEFAULT_IMGSZ     = 640


class DetectionPipeline:
    """YOLOv8s + Ultralytics native tracking. Emits structured events."""

    def __init__(self, model_path: str = "yolov8s.pt", device: str = "0"):
        self.model    = YOLO(model_path)
        self.device   = device
        self.use_half = str(device).isdigit() or device.startswith("cuda")
        self.global_reid = ReIDTracker(clip_type="global")
        self.line_tracker = LineTracker(tracker_name="entry_exit")  # For entry/exit detection
        self.billing_queue_tracker = LineTracker(line_y_norm=0.75, tracker_name="billing_queue")  # For billing queue joins

    def process_video(
        self,
        video_path:     str,
        clip_type:      str,
        store_id:       str  = "STORE_001",
        fps:            Optional[int]  = None,
        vid_stride:     int  = 3,
        conf_threshold: float = DEFAULT_CONF,
        imgsz:          int   = DEFAULT_IMGSZ,
    ) -> list[dict]:
        
        cap       = cv2.VideoCapture(video_path)
        video_fps = fps or (cap.get(cv2.CAP_PROP_FPS) or 30.0)
        cap.release()

        clip_start  = datetime.utcnow()
        tracker_cfg = TRACKER_CONFIG.get(clip_type, "bytetrack.yaml")

        session_mgr = SessionManager()
        reid        = self.global_reid
        emitter     = EventEmitter(store_id=store_id)
        
        # Reset line trackers for new video (entry/exit and billing queue detection)
        self.line_tracker.reset()
        self.billing_queue_tracker.reset()

        events:      list[dict]                              = []
        processed    = 0
        current_billing_visitors: set[str] = set()
        staff_cache: Dict[int, tuple[bool, float, Optional[str]]] = {}

        logger.info(
            "▶ %s  clip_type=%s  tracker=%s  fps=%.1f  stride=%d",
            video_path, clip_type, tracker_cfg, video_fps, vid_stride,
        )

        results_stream = self.model.track(
            source      = video_path,
            stream      = True,
            persist     = True,
            tracker     = tracker_cfg,
            classes     = [COCO_PERSON_CLASS],
            conf        = conf_threshold,
            imgsz       = imgsz,
            half        = self.use_half,
            device      = self.device,
            vid_stride  = vid_stride,
            verbose     = False,
        )

        for result in results_stream:
            frame_idx = processed * vid_stride
            frame     = result.orig_img
            fh, fw    = frame.shape[:2]
            boxes     = result.boxes

            if boxes is not None and boxes.id is not None:
                xyxy  = boxes.xyxy.cpu().numpy()
                ids   = boxes.id.cpu().numpy().astype(int)
                confs = boxes.conf.cpu().numpy()
                
                # Detect line crossings (entry/exit or billing queue)
                crossing_events = {}  # Initialize empty dict
                billing_queue_crossings = {}  # Initialize empty dict
                
                if clip_type in ["entry", "floor"]:
                    crossing_events = self.line_tracker.process_frame(ids, xyxy, fh)
                elif clip_type == "billing":
                    billing_queue_crossings = self.billing_queue_tracker.process_frame(ids, xyxy, fh)

                valid_detections = []
                frame_staff_count = 0

                # ── FIRST PASS: Cache classification securely to fix Bug 4 (Double-counting) ──
                for (x1, y1, x2, y2), track_id, conf in zip(xyxy, ids, confs):
                    x1c, y1c = max(0, int(x1)), max(0, int(y1))
                    x2c, y2c = min(fw, int(x2)), min(fh, int(y2))
                    w, h = x2c - x1c, y2c - y1c
                    
                    if w <= 0 or h <= 0:
                        continue
                    
                    valid_detections.append((x1c, y1c, x2c, y2c, w, h, track_id, conf))

                    if track_id not in staff_cache:
                        crop = frame[y1c:y2c, x1c:x2c]
                        try:
                            camera_id = CLIP_TYPE_TO_CAMERA.get(clip_type, "CAM_1")
                            now_epoch = clip_start.timestamp() + frame_idx / video_fps
                            
                            staff_conf = is_staff_vit(
                                person_crop=crop,
                                bbox=(x1c, y1c, x2c, y2c),
                                clip_type=clip_type,
                                frame_height=fh,
                                track_id=track_id,
                                camera_id=camera_id,
                                timestamp=now_epoch
                            )
                            is_staff   = staff_conf > 0.5
                            staff_registry = get_staff_registry()
                            
                            # FIX BUG-1: Correct dictionary access
                            staff_id = staff_registry.track_to_staff_id.get(track_id, None)
                            
                            staff_cache[track_id] = (is_staff, staff_conf, staff_id)
                        except Exception as e:
                            logger.warning("Staff detection failed: %s, assuming customer", e)
                            staff_cache[track_id] = (False, 0.0, None)

                    # Accurately count staff based on the updated cache
                    if staff_cache[track_id][0]:
                        frame_staff_count += 1

                # ── SECOND PASS: Trackers, Sessions, and Event Emission ──
                for x1c, y1c, x2c, y2c, w, h, track_id, conf in valid_detections:
                    crop = frame[y1c:y2c, x1c:x2c]
                    is_staff, staff_conf, staff_id = staff_cache[track_id]
                    now_epoch = clip_start.timestamp() + frame_idx / video_fps
                    
                    # FIX BUG-2, BUG-3, BUG-7: Use session_mgr to block frame-by-frame ID generation
                    # get_or_create_session returns (visitor_id, session_dict)
                    session_visitor_id, session_info = session_mgr.get_or_create_session(
                        int(track_id),
                        is_staff
                    )
                    
                    # Use the visitor_id from session if available, otherwise generate via Re-ID
                    visitor_id = session_visitor_id
                    is_reentry = False

                    # Only run Re-ID if this track hasn't been assigned an ID yet
                    if not visitor_id:
                        matched_visitor_id, sim = reid.match_reentry(crop, now_epoch)

                        if matched_visitor_id is not None and sim >= reid.match_threshold:
                            is_reentry = True
                            visitor_id = matched_visitor_id
                            logger.info("[%s] Cross-camera MATCH: %s (sim=%.3f thresh=%.2f)", clip_type, visitor_id, sim, reid.match_threshold)
                        else:
                            visitor_id = f"VIS_{track_id}_{int(now_epoch)}"
                            logger.debug("[%s] NEW visitor: %s (best_sim=%.3f thresh=%.2f)", clip_type, visitor_id, sim, reid.match_threshold)

                    frame_time      = frame_idx / video_fps
                    event_timestamp = clip_start + timedelta(seconds=frame_time)

                    # Queue depth logic based on accurate pass-1 staff counts
                    if clip_type == "billing" and not is_staff:
                        total_people = len(valid_detections)
                        queue_depth = max(0, total_people - frame_staff_count)
                    else:
                        queue_depth = None
                    
                    if clip_type == "billing" and is_staff:
                        continue
                    
                    if clip_type == "billing" and not is_staff:
                        current_billing_visitors.add(visitor_id)

                    # Get crossing event for this track
                    crossing_event = None
                    if clip_type in ["entry", "floor"]:
                        crossing_event = crossing_events.get(track_id)
                    elif clip_type == "billing":
                        crossing_event = billing_queue_crossings.get(track_id)
                    
                    event_dict = emitter.emit(
                        track_id        = int(track_id),
                        visitor_id      = visitor_id,
                        clip_type       = clip_type,
                        frame_idx       = frame_idx,
                        video_fps       = video_fps,
                        event_timestamp = event_timestamp,
                        conf            = float(conf),
                        is_staff        = is_staff,
                        staff_conf      = staff_conf,
                        session_info    = session_info if isinstance(session_info, dict) else session_info.__dict__ if hasattr(session_info, '__dict__') else {},
                        frame           = frame,
                        bbox            = (x1c, y1c, w, h),
                        queue_depth     = queue_depth,
                        is_reentry      = is_reentry,
                        crossing_event  = crossing_event,
                    )
                    
                    if event_dict is not None:
                        events.append(event_dict)
                        if event_dict["event_type"] == "EXIT":
                            reid.store_exit(visitor_id, crop, now_epoch)
                            session_mgr.mark_exit(int(track_id), event_timestamp)

            processed += 1

        # ── Post-processing ──
        if clip_type == "billing" and processed > 0:
            final_timestamp = clip_start + timedelta(seconds=processed * vid_stride / video_fps)
            
            for visitor_id in list(emitter.zone_enter_time.keys()):
                if visitor_id not in current_billing_visitors:
                    zone_exit_event = emitter.emit_zone_exit(visitor_id, final_timestamp)
                    if zone_exit_event:
                        events.append(zone_exit_event)
                        
            pos_conversions: Dict[str, float] = {}
            abandon_events = emitter.check_queue_abandons(
                current_billing_visitors, final_timestamp, pos_conversions
            )
            events.extend(abandon_events)

        logger.info("✓ %d frames processed (stride=%d) → %d events", processed, vid_stride, len(events))
        return events


def main():
    parser = argparse.ArgumentParser(description="Retail CCTV detection pipeline")
    parser.add_argument("--video",      required=True)
    parser.add_argument("--clip-type",  required=True, choices=["entry","floor","billing"])
    parser.add_argument("--output",     default="events.jsonl")
    parser.add_argument("--store-id",   default="STORE_001")
    parser.add_argument("--model",      default="yolov8s.pt")
    parser.add_argument("--device",     default="0")
    parser.add_argument("--vid-stride", type=int,   default=3)
    parser.add_argument("--conf",       type=float, default=DEFAULT_CONF)
    parser.add_argument("--imgsz",      type=int,   default=DEFAULT_IMGSZ)
    parser.add_argument("--fps",        type=int,   default=None)
    args = parser.parse_args()

    pipeline = DetectionPipeline(model_path=args.model, device=args.device)
    events   = pipeline.process_video(
        video_path     = args.video,
        clip_type      = args.clip_type,
        store_id       = args.store_id,
        fps            = args.fps,
        vid_stride     = args.vid_stride,
        conf_threshold = args.conf,
        imgsz          = args.imgsz,
    )

    with open(args.output, "a") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

if __name__ == "__main__":
    main()