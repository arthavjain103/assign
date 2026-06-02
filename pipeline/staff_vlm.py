"""
Staff Detection Pipeline 

Logic:
1. Person must be INSIDE the store (checked via entry line on CAM_3)
2. CAM_4 (back-office): Always classified as STAFF when in back-office zone
3. Other cameras: Dark torso ratio ≥ 55% triggers STAFF label (black uniform heuristic)
4. StaffRegistry: Deduplicates same staff member across cameras and track-ID churn

Uses:
- Entry line detection (inside/outside gate)
- Black uniform heuristic (dark torso HSV analysis)
- Back-office zone polygon (CAM_4 only)
- Staff body signature matching across cameras
"""

import cv2
import numpy as np
import logging
from typing import Tuple, List, Optional, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CAMERA CONFIGURATIONS
# ─────────────────────────────────────────────

# CAM_3 entry line (y-coordinate, normalized 0-1): above = OUTSIDE, below = INSIDE
ENTRY_LINE_Y_NORM = 0.55

# Back-office zone polygon for CAM_4
BACK_OFFICE_POLYGON = [
    (0, 200),    # top-left
    (640, 180),  # top-right
    (640, 480),  # bottom-right
    (0, 480)     # bottom-left
]

# Staff zone polygon (for billing area reference)
STAFF_ZONE_POLYGON = [
    (80, 120),   # top-left
    (320, 100),  # top-right
    (350, 420),  # bottom-right
    (60, 450)    # bottom-left
]



class StaffRegistry:
    """Deduplicates staff across cameras and track-ID churn."""
    
    def __init__(self):
        self.staff_id_counter = 0
        # staff_id → {body_signature, last_seen_time, cameras_seen}
        self.registry: Dict[str, dict] = {}
        # track_id → staff_id mapping
        self.track_to_staff_id: Dict[int, str] = {}
    
    def generate_staff_id(self) -> str:
        """Generate unique staff ID."""
        self.staff_id_counter += 1
        return f"STAFF_{self.staff_id_counter:03d}"
    
    def register_or_match_staff(
        self,
        track_id: int,
        body_signature: np.ndarray,
        camera_id: str,
        timestamp: float
    ) -> str:
        """
        Register new staff or match to existing via body signature.
        Returns staff_id.
        """
        # Check if track_id already known
        if track_id in self.track_to_staff_id:
            staff_id = self.track_to_staff_id[track_id]
            self.registry[staff_id]["last_seen_time"] = timestamp
            if camera_id not in self.registry[staff_id]["cameras_seen"]:
                self.registry[staff_id]["cameras_seen"].add(camera_id)
            return staff_id
        
        # Try to match body signature to existing staff
        matched_staff_id = self._match_body_signature(body_signature)
        if matched_staff_id:
            staff_id = matched_staff_id
            self.track_to_staff_id[track_id] = staff_id
            self.registry[staff_id]["last_seen_time"] = timestamp
            if camera_id not in self.registry[staff_id]["cameras_seen"]:
                self.registry[staff_id]["cameras_seen"].add(camera_id)
            logger.info(f"Staff ID {staff_id} matched across camera {camera_id}")
            return staff_id
        
        # Register as new staff member
        staff_id = self.generate_staff_id()
        self.registry[staff_id] = {
            "body_signature": body_signature,
            "last_seen_time": timestamp,
            "cameras_seen": {camera_id}
        }
        self.track_to_staff_id[track_id] = staff_id
        logger.info(f"New staff member registered: {staff_id}")
        return staff_id
    
    def _match_body_signature(
        self,
        body_signature: np.ndarray,
        threshold: float = 0.72
    ) -> Optional[str]:
        """Match body signature using cosine similarity."""
        best_match = None
        best_sim = 0.0
        
        for staff_id, info in self.registry.items():
            existing_sig = info["body_signature"]
            # Cosine similarity
            sim = self._cosine_similarity(body_signature, existing_sig)
            if sim > best_sim and sim >= threshold:
                best_sim = sim
                best_match = staff_id
        
        return best_match
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) == 0 or len(b) == 0:
            return 0.0
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot_product / (norm_a * norm_b))
    
    def get_unique_staff_count(self) -> int:
        """Return unique staff count."""
        return len(self.registry)


# Global staff registry instance
_staff_registry = StaffRegistry()

def point_in_polygon(point: Tuple[int, int], polygon: List[Tuple[int, int]]) -> bool:
    """Check if point is inside polygon using OpenCV."""
    poly_np = np.array(polygon, dtype=np.int32)
    return cv2.pointPolygonTest(poly_np, point, False) >= 0


def is_inside_store(
    bbox: Tuple[float, float, float, float],
    clip_type: str,
    frame_height: Optional[int] = None
) -> bool:
    """
    Determine if person is INSIDE the store using entry line (CAM_3 only).
    
    On CAM_3: Entry line at y = ENTRY_LINE_Y_NORM * frame_height
    - Above line → OUTSIDE
    - Below line → INSIDE
    """
    if clip_type != "entry" or frame_height is None:
        return True  # Assume inside on non-entry cameras
    
    x1, y1, x2, y2 = bbox
    # Centroid y-coordinate
    cy = (y1 + y2) / 2.0
    entry_line_y = ENTRY_LINE_Y_NORM * frame_height
    
    return cy >= entry_line_y  # Below line = inside


def compute_dark_torso_ratio(person_crop: np.ndarray) -> float:
    """
    Compute dark torso ratio: fraction of pixels in torso region with dark color.
    
    Returns: ratio 0.0-1.0
    Heuristic: dark torso (black uniform) ≥ 0.55 → staff
    """
    if person_crop is None or person_crop.size == 0:
        return 0.0
    
    # Convert to HSV
    hsv = cv2.cvtColor(person_crop, cv2.COLOR_BGR2HSV)
    
    # Define "dark" pixels: low saturation AND low value (V < 100)
    # This captures black/dark gray pixels (uniforms)
    dark_mask = (hsv[:, :, 1] < 100) & (hsv[:, :, 2] < 100)
    
    dark_pixels = np.sum(dark_mask)
    total_pixels = person_crop.shape[0] * person_crop.shape[1]
    
    if total_pixels == 0:
        return 0.0
    
    ratio = float(dark_pixels) / float(total_pixels)
    return min(1.0, ratio)


def is_in_back_office(
    bbox: Tuple[float, float, float, float],
    clip_type: str
) -> bool:
    """
    Check if person is in back-office zone (CAM_4 only).
    """
    if clip_type != "back_office":
        return False
    
    x1, y1, x2, y2 = bbox
    cx = int((x1 + x2) / 2)
    cy = int((y1 + y2) / 2)
    
    return point_in_polygon((cx, cy), BACK_OFFICE_POLYGON)

def classify_staff(
    person_crop: np.ndarray,
    bbox: Tuple[float, float, float, float],
    clip_type: str,
    track_id: int,
    frame_height: Optional[int] = None,
    camera_id: str = "CAM_1",
    timestamp: float = 0.0
) -> Tuple[bool, float, Optional[str]]:
    """
    Classify if person is STAFF based on multi-step logic.
    
    Returns:
        (is_staff: bool, confidence: float, staff_id: Optional[str])
    
    Logic:
    1. Check if INSIDE store (entry line for CAM_3)
    2. If CAM_4 (back-office): Check back-office zone
    3. Otherwise: Check dark torso ratio ≥ 55% (black uniform)
    4. Register/match via StaffRegistry for cross-camera dedup
    """
    
    # Step 1: Check if inside store
    if not is_inside_store(bbox, clip_type, frame_height):
        logger.debug(f"[{camera_id}] Person OUTSIDE store (entry line)")
        return False, 0.0, None
    
    # Step 2: Back-office check (CAM_4)
    if clip_type == "back_office" and is_in_back_office(bbox, clip_type):
        logger.debug(f"[{camera_id}] Staff in back-office zone")
        # Compute body signature for registry
        body_sig = _compute_body_signature(person_crop)
        staff_id = _staff_registry.register_or_match_staff(
            track_id, body_sig, camera_id, timestamp
        )
        return True, 0.95, staff_id
    
    # Step 3: Dark torso ratio (uniform heuristic) for other cameras
    dark_ratio = compute_dark_torso_ratio(person_crop)
    if dark_ratio >= 0.55:
        logger.debug(f"[{camera_id}] Staff via uniform (dark_ratio={dark_ratio:.2f})")
        body_sig = _compute_body_signature(person_crop)
        staff_id = _staff_registry.register_or_match_staff(
            track_id, body_sig, camera_id, timestamp
        )
        return True, min(1.0, dark_ratio), staff_id
    
    return False, 0.0, None


def _compute_body_signature(person_crop: np.ndarray) -> np.ndarray:
    """
    Compute body signature (HSV histogram) for cross-camera staff matching.
    
    Returns: 1D array suitable for cosine similarity.
    """
    if person_crop is None or person_crop.size == 0:
        return np.array([])
    
    # Convert to HSV and compute histogram
    hsv = cv2.cvtColor(person_crop, cv2.COLOR_BGR2HSV)
    
    # Compute histogram: 8 hue bins, 8 saturation bins, 8 value bins
    hist = cv2.calcHist(
        [hsv], [0, 1, 2], None,
        [8, 8, 8],
        [0, 180, 0, 256, 0, 256]
    )
    
    # Flatten and normalize
    hist = cv2.normalize(hist, hist).flatten()
    return hist


def is_staff_histogram(
    person_crop: np.ndarray,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    clip_type: Optional[str] = None,
    track_id: int = -1,
    frame_height: Optional[int] = None,
    camera_id: str = "CAM_1",
    timestamp: float = 0.0
) -> float:
    """
    Legacy wrapper for backward compatibility.
    Returns: confidence score (0.0 → 1.0)
    """
    if bbox is None or clip_type is None:
        return 0.0
    
    is_staff, confidence, _ = classify_staff(
        person_crop, bbox, clip_type, track_id, frame_height, camera_id, timestamp
    )
    
    return confidence if is_staff else 0.0


def is_staff_vit(
    person_crop: np.ndarray,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    clip_type: Optional[str] = None,
    staff_zone_polygon: Optional[List[Tuple[int, int]]] = None,
    frame_width: Optional[int] = None,
    frame_height: Optional[int] = None,
    use_vlm: bool = False,
    track_id: int = -1,
    camera_id: str = "CAM_1",
    timestamp: float = 0.0
) -> float:
    """
    Main entry point (new implementation).
    
    Returns: confidence score (0.0 → 1.0)
    """
    if bbox is None or clip_type is None:
        logger.warning("Missing inputs → default non-staff")
        return 0.0
    
    is_staff, confidence, _ = classify_staff(
        person_crop, bbox, clip_type, track_id, frame_height, camera_id, timestamp
    )
    
    return confidence if is_staff else 0.0


def get_staff_registry() -> StaffRegistry:
    """Get the global staff registry instance."""
    return _staff_registry