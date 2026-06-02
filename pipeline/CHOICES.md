# CHOICES.md — Tracker Selection for Multi-Camera Retail Intelligence Pipeline

## Context

This document records the architectural decision-making process for the tracking layer of
the Store Intelligence System built for Apex Retail. The system processes CCTV footage from
3 camera angles per store (Entry, Main Floor, Billing Area) and must assign a consistent
`visitor_token` to each customer across all three feeds.

The actual implementation is in `pipeline/detect.py`, `pipeline/tracker.py`, and
`pipeline/emit.py`. This document explains every decision made in that code.

---

## The Core Problem

Multi-camera person tracking is not one problem — it is two distinct problems stacked together:

1. **Intra-camera tracking** — maintaining a consistent local ID for a person within a
   single camera's video stream across frames.
2. **Inter-camera Re-ID** — matching the same person's identity across two or more
   non-overlapping camera feeds.

Every tracker evaluation below was done against both dimensions separately, because
conflating them leads to wrong architectural decisions — and I made that mistake once
in an earlier draft of this document, which is why this section exists with explicit findings.

---

## Trackers Examined

### 1. SORT (Simple Online and Realtime Tracking)

SORT uses a Kalman filter for motion prediction and the Hungarian algorithm for
assignment. It is fast and simple but relies entirely on IoU overlap with no appearance
model. In retail environments with shelves, counters, and partial occlusions, SORT
produces a high rate of ID switches whenever a person is briefly hidden behind a shelf
or another person.

**Verdict:** Eliminated. No appearance model means it cannot survive even moderate
occlusions in a store environment.

---

### 2. DeepSORT (Deep SORT)

DeepSORT extends SORT by adding a deep appearance descriptor — a CNN trained on the
MARS Re-ID dataset — that produces a 128-dimensional embedding per detection. The
Kalman filter handles motion, and the appearance embedding handles re-association
after occlusion.

**What I examined:**

- DeepSORT's Re-ID gallery operates within a single camera session. It does not
  maintain embeddings across camera handoffs — the gallery is local to each tracker
  instance.
- In comparative benchmarks (Veroke 2025), DeepSORT "can struggle when objects look
  very similar or under heavy occlusion" and "lacks explicit camera-motion compensation
  and advanced re-acquisition logic."
- In multiple multi-camera papers (ScienceDirect 2025, CVPR AICity 2024), DeepSORT
  is used as the intra-camera tracker only — a separate Re-ID module handles
  cross-camera matching.
- Per-frame CNN inference overhead is higher than motion-only trackers.

**Key finding:** DeepSORT is not a cross-camera Re-ID solution. Its appearance
embeddings operate within a single-camera context. I initially stated in an earlier
draft that DeepSORT should be used for cross-camera matching. That was incorrect and
is retracted here. Cross-camera matching requires a dedicated Re-ID model regardless
of which intra-camera tracker is used.

**Verdict:** Not selected. Replaced by ByteTrack (entry/floor) and BoT-SORT (billing)
for intra-camera work, with OSNet handling cross-camera Re-ID separately.

---

### 3. ByteTrack

ByteTrack's key insight is that low-confidence detections — which SORT and DeepSORT
discard — often correspond to partially occluded persons. ByteTrack runs two
association passes:

- First pass: high-confidence detections, IoU + Kalman filter.
- Second pass: remaining unmatched tracks are associated with low-confidence detections.

It does not use an appearance model internally, which keeps it extremely fast.

**What I examined:**

- Pandya & Chauhan (IJEEE 2024) validated YOLOv8 + ByteTrack specifically for
  multi-camera pedestrian tracking, running independent ByteTrack instances per camera
  in parallel threads, achieving MOTA 75.60% and MOTP 86.8%.
- Ultralytics academy documentation confirms: "ByteTrack — fast, simple, great default"
  for static camera setups, which is the case for entry and floor cameras.
- The two-pass low-confidence recovery is directly relevant to retail — people partially
  hidden behind cosmetics shelves still produce low-confidence boxes that ByteTrack
  recovers.
- Native integration via `model.track(tracker="bytetrack.yaml")` — zero additional
  dependencies.

**Verdict:** Selected for Entry and Main Floor cameras (TRACKER_CONFIG in detect.py).

---

### 4. BoT-SORT and BoT-SORT-ReID

BoT-SORT (Aharon et al., 2022) combines IoU-based motion association with optional
Re-ID appearance embeddings and camera-motion compensation. It is built on top of
ByteTrack and extends it with:

- An 8-dimensional Kalman filter state vector (includes width and height, unlike
  ByteTrack's 4-dim).
- Optional Re-ID encoder with EMA feature smoothing (curr_feat and smooth_feat vectors).
- Camera-motion compensation via ECC.

On MOT17: 80.5 MOTA, 80.2 IDF1, 65.0 HOTA — first place on MOTChallenge at time of
publication.

**What I examined:**

The billing area is the densest zone in the store — multiple people standing close
together, limited movement, overlapping bounding boxes. This is exactly the scenario
where ByteTrack's motion-only association starts producing ID switches, because IoU
overlap between nearly-stationary adjacent people becomes ambiguous.

Labellerr (2025) on BoT-SORT: "improves bounding-box prediction, compensates for
camera motion, and uses smarter matching of motion and appearance, resulting in more
accurate and stable tracking in crowded or moving-camera scenarios."

Ultralytics confirms: "BoT-SORT — slower, robust to occlusion (uses appearance
features)."

**Important caveat on Ultralytics built-in BoT-SORT ReID:** The Ultralytics GitHub
discussion thread (Issue #19784) explicitly states: "The current architecture doesn't
maintain long-term embeddings between full disappearances. For persistent tracking
across long occlusions, you'd need to implement a custom ReID system with external
memory beyond the trackers' native capabilities." This means Ultralytics' `botsort.yaml`
ReID is useful for intra-camera occlusion recovery but is NOT a production cross-camera
ReID solution.

**Verdict:** Selected for Billing camera only (TRACKER_CONFIG in detect.py). The
appearance model earns its overhead specifically in the queue zone. Not used for
entry/floor where ByteTrack is faster and sufficient.

---

### 5. StrongSORT

StrongSORT (Du et al., 2023, IEEE Transactions on Multimedia) applies engineering
improvements to DeepSORT: stronger Re-ID feature extractor, camera-motion compensation
via ECC, NSA Kalman filter, and EMA feature updating.

**What I examined:**

- Strong IDF1 scores on MOT benchmarks but no native Ultralytics support.
- Same cross-camera limitation as DeepSORT.
- Integration complexity not justified given ByteTrack + BoT-SORT already cover
  this pipeline's intra-camera needs.

**Verdict:** Not selected.

---

## Per-Camera Tracker Decision (as implemented in detect.py)

```python
TRACKER_CONFIG = {
    "entry":   "bytetrack.yaml",   # clean entry line, fast motion, no queue
    "floor":   "bytetrack.yaml",   # open floor, shelf occlusions, speed matters
    "billing": "botsort.yaml",     # dense queue, stationary people, appearance needed
}
```

This is not arbitrary — it reflects the physical characteristics of each camera zone:

| Camera  | Scene characteristics          | Why this tracker              |
| ------- | ------------------------------ | ----------------------------- |
| Entry   | Single-file motion, clear IoU  | ByteTrack — speed + two-pass  |
| Floor   | Moving through aisles, shelves | ByteTrack — two-pass recovery |
| Billing | Queue, dense, stationary crowd | BoT-SORT — appearance model   |

---

## The Cross-Camera Re-ID Decision

None of the trackers above solve cross-camera identity by themselves. The research
consensus across Pandya & Chauhan (IJEEE 2024), CVPR AICity 2024 papers, and Nunes
et al. (Applied Sciences 2023) is consistent:

> An intra-camera tracker assigns local IDs within one feed. Cross-camera identity
> matching requires a separate appearance embedding model that builds a shared gallery
> across all cameras.

**What I examined for the Re-ID module:**

- **HSV histogram (current implementation in tracker.py `_embed()`):** 48-dimensional
  vector. Fast, zero dependencies, but fails when two people wear similar-colored
  clothing. Not production-grade. Kept as an MVP placeholder.
- **DeepSORT's built-in CNN:** MARS-trained, 128-dim. Better than histogram but
  designed for single-camera use; appearance drift across cameras is a documented
  limitation.
- **OSNet (Omni-Scale Network):** Validated in CVPR AICity 2024 multi-camera
  challenge. Handles scale, viewpoint, and lighting variation via omni-scale feature
  learning. Available via `torchreid`. 512-dim embeddings.
- **FastReID:** Meta AI's production Re-ID library, used in original BoT-SORT-ReID
  paper. Supports multiple backbones, Market-1501 and MSMT17 training.

**Current state in codebase:** `ReIDTracker._embed()` uses HSV histogram. This is
explicitly documented as an MVP placeholder in the code comment:
`"Swap for an OSNet/torchreid embedding in production."`

**Target state:** Replace `_embed()` with OSNet via `torchreid.utils.FeatureExtractor`
pre-trained on Market-1501, cosine similarity threshold 0.45, rolling gallery of last
20 embeddings per `visitor_token`.

---

## Final Architecture Decision

```
3 camera feeds per store
        │
        ├── Entry camera    → YOLOv8s → ByteTrack  → local_id + crop
        ├── Main floor cam  → YOLOv8s → ByteTrack  → local_id + crop
        └── Billing camera  → YOLOv8s → BoT-SORT   → local_id + crop
                                               │
                            ReIDTracker.match_reentry()
                            (HSV histogram → OSNet upgrade path)
                            cosine similarity gallery, threshold=0.45
                                               │
                                    global visitor_token
                                               │
                            SessionManager → EventEmitter → events.jsonl
```

**YOLOv8 model variant:** `yolov8s` (as implemented)
**Reason:** YOLOv8s balances speed and accuracy for 640×640 inference on a T4 GPU
with vid_stride=3. Wang et al. (Sensors 2025) validated YOLOv8n for lightweight
edge deployment; for server-side docker-compose deployment, YOLOv8s gives better
mAP on partially occluded persons in crowded retail scenes.

**conf=0.25 floor (as implemented):**
Intentionally kept low per the problem statement's requirement to not suppress
low-confidence events — they are flagged downstream via the confidence field in
the event schema, not silently dropped.

---

## What Was Rejected and Why

| Option                                     | Rejected Because                                                   |
| ------------------------------------------ | ------------------------------------------------------------------ |
| SORT                                       | No appearance model; fails on any occlusion                        |
| DeepSORT for cross-camera                  | Gallery is intra-camera scoped; documented limitation              |
| ByteTrack for billing zone                 | Motion-only fails in stationary dense queues                       |
| BoT-SORT for entry/floor                   | Appearance overhead not justified; ByteTrack sufficient            |
| StrongSORT                                 | No native Ultralytics support; same cross-camera limit as DeepSORT |
| Ultralytics BoT-SORT ReID for cross-camera | Explicitly experimental per Ultralytics Issue #19784               |
| Single tracker across all cameras          | Architecturally incorrect — cameras are non-overlapping            |

---

## References

1. Zhang Y. et al. — _ByteTrack: Multi-Object Tracking by Associating Every Detection Box_,
   ECCV 2022. arxiv.org/abs/2110.06864

2. Aharon N. et al. — _BoT-SORT: Robust Associations Multi-Pedestrian Tracking_, 2022.
   arxiv.org/abs/2206.14651

3. Pandya N.A., Chauhan N.C. — _Multi-Camera Person Tracking: Integrating YOLOv8 with
   ByteTrack_, IJEEE 11(10), 2024.
   internationaljournalssrg.org/IJEEE/2024/Volume11-Issue10/IJEEE-V11I10P106.pdf

4. Nunes L. et al. — _Multi-Camera Person Re-Identification Based on Trajectory Data_,
   Applied Sciences 2023. DOI: 10.3390/app132011578

5. Du Y. et al. — _StrongSORT: Make DeepSORT Great Again_,
   IEEE Transactions on Multimedia 2023.

6. Ultralytics GitHub Discussion #19784 — BoT-SORT ReID limitations in production.
   github.com/orgs/ultralytics/discussions/19784

7. Labellerr 2025 — _BoT-SORT: Robust Tracking_, labellerr.com/blog/bot-sort-tracking

8. Veroke 2025 — _How Top AI Multi-Object Trackers Perform in Real-World Scenarios_,
   veroke.com/insights/how-top-ai-multi-object-trackers-perform-in-real-world-scenarios

9. Wang Q. et al. — _A Lightweight Person Detector for Surveillance Footage Based on
   YOLOv8n_, Sensors 2025. DOI: 10.3390/s25020436

10. ICIIT 2025 — _Robust Multi-Camera Tracking with YOLOv10 and OSNet_.
    ACM DL 10.1145/3731763.3731778
