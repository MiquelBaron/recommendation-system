import hashlib
import logging
import os
import time
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Double, Index, String, Text, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.models.schemas import Event, UserVectorState
from app.storage.postgres_client import SessionLocal, get_postgres_engine

logger = logging.getLogger(__name__)

POSTGRES_ENABLED = os.getenv("POSTGRES_ENABLED", "0").strip().lower() in {
    "1",
    "true",
    "yes",
}

class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ItemRow(Base):
    __tablename__ = "items"

    item_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_user_event_ts_desc", "user_id", "event_ts"),
        Index("idx_events_received_ts_desc", "received_ts"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)
    user_id: Mapped[str] = mapped_column(Text)
    item_id: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    event_ts: Mapped[float] = mapped_column(Double)
    received_ts: Mapped[float] = mapped_column(Double)
    source: Mapped[str] = mapped_column(Text, default="api", server_default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserVectorSnapshotRow(Base):
    __tablename__ = "user_vector_snapshots"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    short_term_vector: Mapped[list[float]] = mapped_column(JSON)
    long_term_vector: Mapped[list[float]] = mapped_column(JSON)
    last_event_ts: Mapped[float | None] = mapped_column(Double, nullable=True)
    snapshot_ts: Mapped[float] = mapped_column(Double)
    version: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


@contextmanager
def _conn():
    conn = SessionLocal()
    try:
        yield conn
        conn.commit()  # type: ignore[attr-defined]
    finally:
        conn.close()


def _event_idempotency_key(event: Event) -> str:
    raw = f"{event.user_id}|{event.item_id}|{event.event_type}|{event.timestamp:.6f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_postgres_schema() -> None:
    if not POSTGRES_ENABLED:
        return
    Base.metadata.create_all(get_postgres_engine())
    logger.info("postgres schema ensured")


def insert_event_durable(event: Event, *, source: str = "api") -> None:
    """Durable event insert with idempotency; duplicates become no-op."""
    if not POSTGRES_ENABLED:
        return
    key = _event_idempotency_key(event)
    now_ts = time.time()
    with _conn() as conn:
        session: Session = conn
        stmt_event = insert(EventRow).values(
            idempotency_key=key,
            user_id=event.user_id,
            item_id=event.item_id,
            event_type=event.event_type,
            event_ts=event.timestamp,
            received_ts=now_ts,
            source=source,
        )
        stmt_event = stmt_event.on_conflict_do_nothing(index_elements=[EventRow.idempotency_key])
        session.execute(stmt_event)

        stmt_user = insert(UserRow).values(user_id=event.user_id)
        stmt_user = stmt_user.on_conflict_do_update(
            index_elements=[UserRow.user_id],
            set_={"updated_at": func.now()},
        )
        session.execute(stmt_user)


def upsert_item_catalog(item_id: str, title: str, metadata: dict[str, object]) -> None:
    if not POSTGRES_ENABLED:
        return
    with _conn() as conn:
        session: Session = conn
        stmt = insert(ItemRow).values(item_id=item_id, title=title, metadata_json=metadata)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ItemRow.item_id],
            set_={
                "title": stmt.excluded.title,
                "metadata": stmt.excluded.metadata,
                "updated_at": func.now(),
            },
        )
        session.execute(stmt)


def upsert_user_vector_snapshot(user_id: str, state: UserVectorState, *, snapshot_ts: float | None = None) -> None:
    if not POSTGRES_ENABLED:
        return
    ts = time.time() if snapshot_ts is None else snapshot_ts
    with _conn() as conn:
        session: Session = conn
        stmt = insert(UserVectorSnapshotRow).values(
            user_id=user_id,
            short_term_vector=state.short_term_vector,
            long_term_vector=state.long_term_vector,
            last_event_ts=state.last_event_ts,
            snapshot_ts=ts,
            version=1,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[UserVectorSnapshotRow.user_id],
            set_={
                "short_term_vector": stmt.excluded.short_term_vector,
                "long_term_vector": stmt.excluded.long_term_vector,
                "last_event_ts": stmt.excluded.last_event_ts,
                "snapshot_ts": stmt.excluded.snapshot_ts,
                "version": UserVectorSnapshotRow.version + 1,
                "updated_at": func.now(),
            },
        )
        session.execute(stmt)


def list_recent_user_vector_snapshots(limit: int = 2000) -> Iterable[tuple[str, UserVectorState]]:
    if not POSTGRES_ENABLED:
        return []
    rows: list[tuple[str, UserVectorState]] = []
    with _conn() as conn:
        session: Session = conn
        stmt = (
            select(
                UserVectorSnapshotRow.user_id,
                UserVectorSnapshotRow.short_term_vector,
                UserVectorSnapshotRow.long_term_vector,
                UserVectorSnapshotRow.last_event_ts,
            )
            .order_by(UserVectorSnapshotRow.snapshot_ts.desc())
            .limit(limit)
        )
        for user_id, short_term, long_term, last_event_ts in session.execute(stmt).all():
            rows.append(
                (
                    user_id,
                    UserVectorState(
                        short_term_vector=[float(x) for x in short_term],
                        long_term_vector=[float(x) for x in long_term],
                        last_event_ts=(
                            float(last_event_ts) if last_event_ts is not None else None
                        ),
                    ),
                )
            )
    return rows
