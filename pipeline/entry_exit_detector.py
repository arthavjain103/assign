"""
Entry/Exit Detection with Vertical Line Crossing Logic
Integrates line-crossing entry/exit counting into the detection pipeline
"""
import cv2
import numpy as np
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Entry line position: y-coordinate as fraction of frame height
ENTRY_LINE_Y_NORM = 0.55  # 55% from top


class LineTracker:
    """
    Tracks people crossing a horizontal line to count entry/exit or queue joins.
    
    Logic:
    - Line at y = line_y_norm * frame_height (horizontal line)
    - Above line (cy < line_y) = OUTSIDE (side = -1)
    - Below line (cy >= line_y) = INSIDE (side = +1)
    - Track centroid crossing: -1 → +1 = ENTRY/QUEUE_JOIN
    - Track centroid crossing: +1 → -1 = EXIT
    
    Args:
        line_y_norm: Y position as fraction of frame height (0.0-1.0)
        tracker_name: Name for logging (e.g., "entry_exit", "billing_queue")
    """
    
    def __init__(self, line_y_norm: float = ENTRY_LINE_Y_NORM, tracker_name: str = "entry_exit"):
        self.line_y_norm = line_y_norm
        self.tracker_name = tracker_name
        self.track_side: Dict[int, int] = {}  # track_id → side (-1=outside, +1=inside)
        self.entry_count = 0
        self.exit_count = 0
    
    def process_frame(
        self,
        track_ids: np.ndarray,
        boxes: np.ndarray,
        frame_height: int
    ) -> Dict[int, str]:
        """
        Process detections in current frame and detect line crossings.
        
        Args:
            track_ids: Array of track IDs
            boxes: Array of bounding boxes (x1, y1, x2, y2)
            frame_height: Height of frame
            
        Returns:
            Dict mapping track_id to event type: 'ENTRY'/'QUEUE_JOIN', 'EXIT', or None
        """
        line_y = int(frame_height * self.line_y_norm)
        crossing_events = {}
        
        for track_id, box in zip(track_ids, boxes):
            x1, y1, x2, y2 = map(int, box)
            
            # Centroid position
            cy = (y1 + y2) // 2
            
            # Current side: -1 (above line = outside), +1 (below line = inside)
            current_side = -1 if cy < line_y else 1
            
            # Check if this is first sighting of this track
            if track_id in self.track_side:
                previous_side = self.track_side[track_id]
                
                # Detect crossing
                if previous_side == -1 and current_side == 1:
                    # Crossed from outside to inside = ENTRY
                    self.entry_count += 1
                    crossing_events[track_id] = 'ENTRY'
                    logger.info(f"[{self.tracker_name.upper()}] ENTRY: Track {track_id} (count: {self.entry_count})")
                    
                elif previous_side == 1 and current_side == -1:
                    # Crossed from inside to outside = EXIT
                    self.exit_count += 1
                    crossing_events[track_id] = 'EXIT'
                    logger.info(f"[{self.tracker_name.upper()}] EXIT: Track {track_id} (count: {self.exit_count})")
            
            # Update tracking state
            self.track_side[track_id] = current_side
        
        return crossing_events
    
    def draw_on_frame(
        self,
        frame: np.ndarray,
        track_ids: np.ndarray,
        boxes: np.ndarray,
        frame_height: int
    ) -> np.ndarray:
        """
        Draw line, bounding boxes, IDs, and counts on frame.
        
        Args:
            frame: Video frame
            track_ids: Array of track IDs
            boxes: Array of bounding boxes (x1, y1, x2, y2)
            frame_height: Height of frame (used to calculate line position)
            
        Returns:
            Annotated frame
        """
        frame = frame.copy()
        h, w = frame.shape[:2]
        line_y = int(h * ENTRY_LINE_Y_NORM)
        
        # Draw horizontal entry/exit line (yellow)
        cv2.line(
            frame,
            (0, line_y),
            (w, line_y),
            (0, 255, 255),  # Yellow (BGR)
            3
        )
        
        # Draw boxes and IDs for each track
        for track_id, box in zip(track_ids, boxes):
            x1, y1, x2, y2 = map(int, box)
            
            # Centroid
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            
            # Bounding box (green)
            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),  # Green
                2
            )
            
            # Track ID label
            cv2.putText(
                frame,
                f"ID {track_id}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )
            
            # Centroid point (red)
            cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
        
        # Draw entry/exit counts
        cv2.putText(
            frame,
            f"ENTRY: {self.entry_count}",
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 255, 0),  # Green
            3
        )
        
        cv2.putText(
            frame,
            f"EXIT: {self.exit_count}",
            (20, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 0, 255),  # Red
            3
        )
        
        return frame
    
    def get_counts(self) -> Tuple[int, int]:
        """Return (entry_count, exit_count)."""
        return self.entry_count, self.exit_count
    
    def reset(self):
        """Reset counts and tracking state."""
        self.track_side.clear()
        self.entry_count = 0
        self.exit_count = 0


# Example usage with detection pipeline
def process_video_with_entry_exit(
    video_path: str,
    model_path: str = "yolov8n.pt",
    output_path: Optional[str] = None,
):
    """
    Process video and count entry/exit with line crossing detection.
    
    Args:
        video_path: Input video file
        model_path: YOLOv8 model path
        output_path: Optional output video path
    """
    from ultralytics import YOLO
    
    model = YOLO(model_path)
    cap = cv2.VideoCapture(video_path)
    
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    logger.info(f"Video: {w}x{h} @ {fps} FPS")
    
    # Setup output video writer if specified
    writer = None
    if output_path:
        writer = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (w, h)
        )
        logger.info(f"Output video: {output_path}")
    
    # Initialize line tracker
    line_tracker = LineTracker()
    
    # Run detection with tracking
    results = model.track(
        source=video_path,
        stream=True,
        persist=True,
        tracker="bytetrack.yaml",
        classes=[0],  # Person class only
        conf=0.3
    )
    
    frame_count = 0
    
    for result in results:
        frame = result.orig_img.copy()
        
        # Process tracking if available
        if result.boxes.id is not None:
            boxes = result.boxes.xyxy.cpu().numpy()
            track_ids = result.boxes.id.cpu().numpy().astype(int)
            
            # Detect entry/exit crossings
            crossing_events = line_tracker.process_frame(
                track_ids,
                boxes,
                h
            )
            
            # Draw annotations
            frame = line_tracker.draw_on_frame(
                frame,
                track_ids,
                boxes,
                h
            )
        else:
            # No detections, just draw the line
            line_y = int(h * ENTRY_LINE_Y_NORM)
            cv2.line(frame, (0, line_y), (w, line_y), (0, 255, 255), 3)
        
        # Write to output video
        if writer:
            writer.write(frame)
        
        frame_count += 1
        
        if frame_count % 30 == 0:
            logger.info(f"Processed {frame_count} frames. Entry: {line_tracker.entry_count}, Exit: {line_tracker.exit_count}")
    
    # Cleanup
    cap.release()
    if writer:
        writer.release()
        logger.info(f"Output saved: {output_path}")
    
    # Final results
    entry_count, exit_count = line_tracker.get_counts()
    logger.info(f"Final: ENTRY = {entry_count}, EXIT = {exit_count}")
    
    return entry_count, exit_count


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python entry_exit_detector.py <video_path> [output_path]")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    entry, exit_count = process_video_with_entry_exit(
        video_path,
        output_path=output_path
    )
    
    print(f"\n✓ Processing complete!")
    print(f"  ENTRY: {entry}")
    print(f"  EXIT: {exit_count}")
