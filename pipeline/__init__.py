"""Pipeline package: detection, tracking, Re-ID, event emission."""

from .detect    import DetectionPipeline
from .tracker   import ReIDTracker, SessionManager
from .emit      import EventEmitter
from .staff_vlm import is_staff_histogram, is_staff_vit, StaffRegistry, classify_staff, get_staff_registry

__all__ = [
    "DetectionPipeline",
    "ReIDTracker",
    "SessionManager",
    "EventEmitter",
    "is_staff_histogram",
    "is_staff_vit",
    "StaffRegistry",
    "classify_staff",
    "get_staff_registry",
]
