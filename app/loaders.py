"""
Data loaders: ingest store_layout.json, pos_transactions.csv, and sample_events.jsonl.
"""
import json
import csv
from datetime import datetime
from pathlib import Path
import logging

from sqlalchemy.orm import Session

from .db import EventDB, POSTransactionDB, StoreLayoutDB
from .models import Event

logger = logging.getLogger(__name__)


def load_store_layout(store_layout_path: Path | str, db: Session) -> None:
    """
    Load store_layout.json into StoreLayoutDB.
    Expected format: { store_id: ..., zones: {...}, open_hours: {...}, cameras: {...} }
    """
    store_layout_path = Path(store_layout_path)
    if not store_layout_path.exists():
        logger.warning(f"store_layout.json not found at {store_layout_path}")
        return

    try:
        with open(store_layout_path) as f:
            layout_data = json.load(f)

        store_id = layout_data.get("store_id")
        if not store_id:
            logger.error("store_layout.json missing store_id")
            return

        # Check if already exists
        existing = db.query(StoreLayoutDB).filter(
            StoreLayoutDB.store_id == store_id
        ).first()

        if existing:
            existing.zones = json.dumps(layout_data.get("zones", {}))
            existing.open_hours = json.dumps(layout_data.get("open_hours", {}))
            existing.cameras = json.dumps(layout_data.get("cameras", {}))
            existing.updated_at = datetime.utcnow()
        else:
            new_layout = StoreLayoutDB(
                store_id=store_id,
                zones=json.dumps(layout_data.get("zones", {})),
                open_hours=json.dumps(layout_data.get("open_hours", {})),
                cameras=json.dumps(layout_data.get("cameras", {})),
            )
            db.add(new_layout)

        db.commit()
        logger.info(f"Loaded store layout for {store_id}")

    except Exception as e:
        logger.exception(f"Failed to load store_layout.json: {e}")
        db.rollback()


def load_pos_transactions(csv_path: Path | str, db: Session) -> None:
    """
    Load pos_transactions.csv.
    Expected columns: store_id, transaction_id, timestamp, basket_value_inr
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.warning(f"pos_transactions.csv not found at {csv_path}")
        return

    try:
        count = 0
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check if already exists
                existing = db.query(POSTransactionDB).filter(
                    POSTransactionDB.transaction_id == row["transaction_id"]
                ).first()

                if existing:
                    continue

                timestamp_str = row["timestamp"]
                timestamp = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                ).replace(tzinfo=None)

                txn = POSTransactionDB(
                    transaction_id=row["transaction_id"],
                    store_id=row["store_id"],
                    timestamp=timestamp,
                    basket_value_inr=float(row["basket_value_inr"]),
                )
                db.add(txn)
                count += 1

        db.commit()
        logger.info(f"Loaded {count} POS transactions")

    except Exception as e:
        logger.exception(f"Failed to load pos_transactions.csv: {e}")
        db.rollback()


def load_sample_events(jsonl_path: Path | str, db: Session) -> None:
    """
    Load sample_events.jsonl (one JSON object per line).
    Each line is a valid Event in the schema.
    """
    jsonl_path = Path(jsonl_path)
    if not jsonl_path.exists():
        logger.warning(f"sample_events.jsonl not found at {jsonl_path}")
        return

    try:
        count = 0
        with open(jsonl_path) as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    event_dict = json.loads(line)
                    event = Event(**event_dict)

                    # Check if already exists
                    existing = db.query(EventDB).filter(
                        EventDB.event_id == event.event_id
                    ).first()

                    if existing:
                        continue

                    timestamp_dt = datetime.fromisoformat(
                        event.timestamp.replace("Z", "+00:00")
                    ).replace(tzinfo=None)

                    db_event = EventDB(
                        event_id=event.event_id,
                        store_id=event.store_id,
                        camera_id=event.camera_id,
                        visitor_id=event.visitor_id,
                        event_type=event.event_type.value,
                        timestamp=timestamp_dt,
                        zone_id=event.zone_id,
                        dwell_ms=event.dwell_ms,
                        is_staff=event.is_staff,
                        confidence=event.confidence,
                        metadata=json.dumps(event.metadata),
                    )
                    db.add(db_event)
                    count += 1

                except Exception as e:
                    logger.error(f"Failed to parse event line: {e}")
                    continue

        db.commit()
        logger.info(f"Loaded {count} sample events")

    except Exception as e:
        logger.exception(f"Failed to load sample_events.jsonl: {e}")
        db.rollback()
