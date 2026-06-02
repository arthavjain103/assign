"""
SQLAlchemy 2.0 database configuration and models.
SQLite with event_id PRIMARY KEY enables idempotent ingest via INSERT OR IGNORE.
"""
import os
from datetime import datetime
from typing import Optional
import json

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./store_intelligence.db")

# Use StaticPool for SQLite (avoids threading issues in tests)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    poolclass=StaticPool if "sqlite" in DATABASE_URL else None,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EventDB(Base):
    """Event table: PRIMARY KEY on event_id for idempotent ingest."""
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, index=True, nullable=False)
    camera_id = Column(String, nullable=False)
    visitor_id = Column(String, index=True, nullable=False)
    event_type = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    zone_id = Column(String, nullable=True, index=True)
    dwell_ms = Column(Integer, default=0)
    is_staff = Column(Boolean, default=False, index=True)
    confidence = Column(Float, default=0.5)
    event_metadata = Column(Text, default="{}")  # JSON serialized (renamed from 'metadata')
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_store_timestamp", "store_id", "timestamp"),
        Index("idx_store_visitor", "store_id", "visitor_id"),
        Index("idx_zone_timestamp", "zone_id", "timestamp"),
    )


class POSTransactionDB(Base):
    """POS transactions for conversion correlation."""
    __tablename__ = "pos_transactions"

    transaction_id = Column(String, primary_key=True, index=True)
    store_id = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    basket_value_inr = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class StoreLayoutDB(Base):
    """Store layout: zones, cameras, open hours."""
    __tablename__ = "store_layout"

    store_id = Column(String, primary_key=True, index=True)
    zones = Column(Text, default="{}")  # JSON serialized
    open_hours = Column(Text, default="{}")  # JSON serialized
    cameras = Column(Text, default="{}")  # JSON serialized
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_db():
    """Dependency injection for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
