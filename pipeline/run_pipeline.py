"""
run_pipeline.py — Top-level runner for all 3 cameras in one store.

Usage:
    python run_pipeline.py \
        --entry   /path/to/entry.mp4 \
        --floor   /path/to/floor.mp4 \
        --billing /path/to/billing.mp4 \
        --store-id STORE_001 \
        --output  events.jsonl

On Kaggle: import and call run_store() directly from the notebook.
"""

import argparse
import json
import logging
from pathlib import Path

from pipeline.detect import DetectionPipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


def run_store(
    entry_video:   str,
    floor_video:   str,
    billing_video: str,
    store_id:      str  = "STORE_001",
    output_path:   str  = "events.jsonl",
    model_path:    str  = "yolov8s.pt",
    device:        str  = "0",
    vid_stride:    int  = 3,
) -> list[dict]:
    """
    Process all 3 camera feeds for one store.
    Returns the combined list of events and writes them to output_path.
    """
    pipeline = DetectionPipeline(model_path=model_path, device=device)

    clips = [
        (entry_video,   "entry"),
        (floor_video,   "floor"),
        (billing_video, "billing"),
    ]

    all_events: list[dict] = []

    for video_path, clip_type in clips:
        if not Path(video_path).exists():
            logger.warning("Video not found, skipping: %s", video_path)
            continue

        logger.info("═══ Processing %s (%s) ═══", video_path, clip_type)
        events = pipeline.process_video(
            video_path  = video_path,
            clip_type   = clip_type,
            store_id    = store_id,
            vid_stride  = vid_stride,
        )
        all_events.extend(events)
        logger.info("  → %d events from %s camera", len(events), clip_type)

    # Sort by timestamp before writing
    all_events.sort(key=lambda e: e["timestamp"])

    with open(output_path, "w") as f:
        for e in all_events:
            f.write(json.dumps(e) + "\n")

    logger.info("✓ Total: %d events written → %s", len(all_events), output_path)
    return all_events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run retail pipeline for one store")
    parser.add_argument("--entry",    required=True, help="Entry camera video path")
    parser.add_argument("--floor",    required=True, help="Floor camera video path")
    parser.add_argument("--billing",  required=True, help="Billing camera video path")
    parser.add_argument("--store-id", default="STORE_001")
    parser.add_argument("--output",   default="events.jsonl")
    parser.add_argument("--model",    default="yolov8s.pt")
    parser.add_argument("--device",   default="0")
    parser.add_argument("--stride",   type=int, default=3)
    args = parser.parse_args()

    run_store(
        entry_video   = args.entry,
        floor_video   = args.floor,
        billing_video = args.billing,
        store_id      = args.store_id,
        output_path   = args.output,
        model_path    = args.model,
        device        = args.device,
        vid_stride    = args.stride,
    )
