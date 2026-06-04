"""
Tracking / Re-ID / session management.

Two classes:
  - ReIDTracker   : cross-clip re-entry matching via appearance embeddings.
                    MVP uses HSV histogram (fast, zero deps).
                    Production upgrade: swap _embed() for OSNet via torchreid.
  - SessionManager: maps native track_id → visitor_id, handles re-entry windows.

Native ByteTrack / BoT-SORT (in detect.py) own frame-to-frame association.
This module handles ONLY the cross-clip / cross-camera layer.
"""
"""
Tracking / Re-ID / session management.

Two classes:
  - ReIDTracker   : cross-clip re-entry matching via appearance embeddings.
                    MVP uses HSV histogram (fast, zero deps).
                    Production upgrade: swap _embed() for OSNet via torchreid.
  - SessionManager: maps native track_id -> visitor_id, handles re-entry windows.

Native ByteTrack / BoT-SORT (in detect.py) own frame-to-frame association.
This module handles ONLY the cross-clip / cross-camera layer.

"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

USE_OSNET = True


def _build_osnet_extractor():
    try:
        import torchreid
        extractor = torchreid.utils.FeatureExtractor(
            model_name   = "osnet_x1_0",
            model_path   = "",
            device       = "cuda",
        )
        logger.info("OSNet extractor loaded (cross-camera Re-ID: production mode)")
        return extractor
    except Exception as e:
        logger.warning("OSNet load failed (%s) — falling back to HSV histogram", e)
        return None


_OSNET_EXTRACTOR = _build_osnet_extractor() if USE_OSNET else None


class ReIDTracker:
    """
    Appearance-based re-entry / cross-clip Re-ID layer.

    Operates ON TOP of native tracker IDs — does NOT replace ByteTrack/BoT-SORT.
    Decides whether a NEW native track_id is actually a returning visitor.

    FIX (Bug 2): `seen_track_ids` tracks which track_ids have already been
    resolved (matched to an existing visitor or assigned a new one). Callers
    must check `is_new_track(track_id)` before calling `match_reentry` to
    avoid running expensive Re-ID on every frame for already-known tracks.
    Alternatively, call the new `resolve_track` helper which encapsulates
    this guard internally.
    """

    def __init__(
        self,
        clip_type:         str   = "entry",
        reentry_window_s:  float = 900.0,
        match_threshold:   float = 0.65,
    ):
        self.clip_type        = clip_type
        self.reentry_window_s = reentry_window_s
        self.match_threshold  = match_threshold
        self.gallery: Dict[int, dict] = {}
        self.exited_visitors: Dict[str, dict] = {}
        # FIX (Bug 2): track_ids that have already been resolved — skip Re-ID
        # for these on subsequent frames to avoid per-frame overhead and
        # accidental identity theft of active visitors.
        self.seen_track_ids: set[int] = set()

    # ── Embedding ─────────────────────────────────────────────────────────────
    @staticmethod
    def _embed_histogram(crop: np.ndarray) -> np.ndarray:
        if crop is None or crop.size == 0:
            return np.zeros(48, dtype=np.float32)
        hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist(
            [hsv], [0, 1, 2], None,
            [4, 4, 3], [0, 180, 0, 256, 0, 256],
        )
        hist = cv2.normalize(hist, hist).flatten().astype(np.float32)
        return hist

    @staticmethod
    def _embed_osnet(crop: np.ndarray) -> np.ndarray:
        if _OSNET_EXTRACTOR is None:
            return ReIDTracker._embed_histogram(crop)
        if crop is None or crop.size == 0:
            return np.zeros(512, dtype=np.float32)
        try:
            feat = _OSNET_EXTRACTOR(crop)
            return feat.cpu().numpy().flatten()
        except Exception as e:
            logger.debug("OSNet embed failed: %s", e)
            return ReIDTracker._embed_histogram(crop)

    @staticmethod
    def _embed(crop: np.ndarray) -> np.ndarray:
        if USE_OSNET and _OSNET_EXTRACTOR is not None:
            return ReIDTracker._embed_osnet(crop)
        return ReIDTracker._embed_histogram(crop)

    # ── Cosine similarity ─────────────────────────────────────────────────────
    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    # ── Public API ────────────────────────────────────────────────────────────
    def is_new_track(self, track_id: int) -> bool:
        """
        Return True if this track_id has never been resolved before.
        Only new tracks should go through match_reentry.
        """
        return track_id not in self.seen_track_ids

    def mark_track_resolved(self, track_id: int) -> None:
        """
        Mark a track_id as resolved so future frames skip Re-ID for it.
        Call this after match_reentry has produced a decision (match or new).
        """
        self.seen_track_ids.add(track_id)

    def on_track_lost(self, track_id: int) -> None:
        """
        Called when ByteTrack drops a track permanently.
        Removes from seen set so a future re-appearance (rare) is treated fresh.
        """
        self.seen_track_ids.discard(track_id)
        self.gallery.pop(track_id, None)

    def store_exit(self, visitor_id: str, crop: np.ndarray, now_epoch: float) -> None:
        """Store visitor embedding on exit for later re-entry matching."""
        emb = self._embed(crop)
        self.exited_visitors[visitor_id] = {
            "embedding": emb,
            "exit_time": now_epoch
        }
        logger.debug("Stored exit embedding for visitor %s", visitor_id)

    def match_reentry(
        self,
        crop:       np.ndarray,
        now_epoch:  float,
    ) -> Tuple[Optional[str], float]:
        """
        Compare crop against exited visitors within re-entry window.
        Should only be called for new (unseen) track_ids — callers must
        check is_new_track() first, or use resolve_track() instead.

        Returns:
            (matched_visitor_id or None, best_similarity_score)
        """
        self.exited_visitors = {
            vid: rec for vid, rec in self.exited_visitors.items()
            if now_epoch - rec["exit_time"] <= self.reentry_window_s
        }

        emb      = self._embed(crop)
        best_id  = None
        best_sim = 0.0
        all_sims = []

        for vid, rec in self.exited_visitors.items():
            sim = self._cosine(emb, rec["embedding"])
            all_sims.append((vid, sim))
            if sim > best_sim:
                best_id, best_sim = vid, sim

        if all_sims:
            logger.debug(
                "ReID pool: %d candidates | best=%.3f (match_thresh=%.2f) | all_sims=%s",
                len(all_sims),
                best_sim,
                self.match_threshold,
                [(v[:8], f"{s:.3f}") for v, s in sorted(all_sims, key=lambda x: -x[1])[:5]]
            )

        if best_sim >= self.match_threshold:
            logger.info("Re-entry match: visitor %s (sim=%.3f)", best_id, best_sim)
            return best_id, best_sim
        return None, best_sim

    def remember(self, track_id: int, crop: np.ndarray, now_epoch: float) -> None:
        """Store / update embedding for a track_id (EMA update)."""
        emb = self._embed(crop)
        if track_id in self.gallery:
            old = self.gallery[track_id]["embedding"]
            emb = 0.9 * old + 0.1 * emb
        self.gallery[track_id] = {"embedding": emb, "last_seen": now_epoch}


# ── Session Manager ───────────────────────────────────────────────────────────
class SessionManager:
    """
    Maps native track_id -> visitor_id and manages session lifecycle.

    Logic:
      - First sighting of track_id -> new visitor_id assigned (ONCE, cached).
      - Subsequent frames with same track_id -> same visitor_id returned from cache.
      - EXIT -> session marked closed, pushed to recent_exits for re-entry matching.
      - REENTRY (Re-ID confident) -> existing visitor_id reused.
    """

    def __init__(self, reentry_window_minutes: int = 15):
        self.track_to_visitor:  Dict[int, str]  = {}
        self.visitor_sessions:  Dict[str, dict] = {}
        self.recent_exits:      List[dict]      = []
        self.reentry_window     = reentry_window_minutes

    def get_or_create_session(
        self, track_id: int, is_staff: bool
    ) -> Tuple[str, dict]:
        """
        Return cached visitor_id for track_id if it already exists.
        Create a new one ONLY on first sighting of this track_id.
        """
        if track_id in self.track_to_visitor:
            vid = self.track_to_visitor[track_id]
            return vid, self.visitor_sessions[vid]

        vid = f"VIS_{track_id}_{int(datetime.utcnow().timestamp())}"
        self.track_to_visitor[track_id] = vid
        self.visitor_sessions[vid] = {
            "entered":   datetime.utcnow(),
            "exited":    None,
            "is_staff":  is_staff,
            "track_ids": [track_id],
        }
        logger.debug("New visitor session: track_id=%d -> %s", track_id, vid)
        return vid, self.visitor_sessions[vid]

    def on_track_lost(self, track_id: int) -> None:
        """Called when ByteTrack/BoT-SORT drops a track permanently."""
        vid = self.track_to_visitor.pop(track_id, None)
        if vid:
            logger.debug("Track %d lost — visitor %s mapping cleared", track_id, vid)

    def mark_exit(self, track_id: int, exit_time: datetime) -> None:
        if track_id in self.track_to_visitor:
            vid = self.track_to_visitor[track_id]
            self.visitor_sessions[vid]["exited"] = exit_time
            self.recent_exits.append({"visitor_id": vid, "exit_time": exit_time})
            cutoff = exit_time - timedelta(minutes=self.reentry_window)
            self.recent_exits = [
                e for e in self.recent_exits if e["exit_time"] > cutoff
            ]

    def reuse_or_new(
        self,
        matched_visitor_id: Optional[str],
        track_id:           int,
        is_staff:           bool,
    ) -> Tuple[str, dict]:
        """
        If Re-ID matched a recent exit -> reuse visitor_id (REENTRY).
        Otherwise -> create a fresh session.
        """
        if matched_visitor_id is not None:
            self.track_to_visitor[track_id] = matched_visitor_id
            sess = self.visitor_sessions[matched_visitor_id]
            sess["track_ids"].append(track_id)
            sess["exited"] = None
            return matched_visitor_id, sess
        return self.get_or_create_session(track_id, is_staff)