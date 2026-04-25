import asyncio
import logging
import os
import time

from redis import Redis

from app.models.schemas import Event
from app.services.user_embedding_service import apply_single_event_to_store
from app.storage.catalog import item_embeddings
from app.storage.postgres_store import (
    POSTGRES_ENABLED,
    ensure_postgres_schema,
    list_recent_user_vector_snapshots,
    upsert_user_vector_snapshot,
)
from app.storage.redis_client import get_redis_client
from app.storage.user_state import (
    CONSUMER_GROUP,
    STREAM_KEY,
    get_user_state,
    get_user_vector_state,
    save_user_vector_state,
)

logger = logging.getLogger(__name__)

CONSUMER = "worker-1"
SNAPSHOT_EVERY_EVENTS = int(os.getenv("SNAPSHOT_EVERY_EVENTS", "10"))
RECOVERY_SNAPSHOT_LIMIT = int(os.getenv("RECOVERY_SNAPSHOT_LIMIT", "2000"))
METRICS_LOG_INTERVAL_SECONDS = int(os.getenv("WORKER_METRICS_LOG_INTERVAL_SECONDS", "30"))

_processed_events = 0
_last_metrics_log_ts = 0.0


def _configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

def init_group(r: Redis) -> None:
    from redis.exceptions import ResponseError

    try:
        r.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def process_event(r: Redis, msg_id: str, data: dict) -> None:
    global _processed_events
    event = Event(
        user_id=data["user_id"],
        item_id=data["item_id"],
        event_type=data["event_type"],
        timestamp=float(data["timestamp"]),
        query=(data.get("query") or None),
    )
    logger.info(
        "event received entry_id=%s user_id=%s item_id=%s event_type=%s timestamp=%s",
        msg_id,
        event.user_id,
        event.item_id,
        event.event_type,
        event.timestamp,
    )
    if event.event_type == "search":
        logger.info(
            "search event received entry_id=%s user_id=%s query=%s",
            msg_id,
            event.user_id,
            event.query,
        )
        apply_single_event_to_store(get_user_state(), event.user_id, event, now_ts=time.time())
        _processed_events += 1
        if POSTGRES_ENABLED and SNAPSHOT_EVERY_EVENTS > 0 and (_processed_events % SNAPSHOT_EVERY_EVENTS == 0):
            state = get_user_vector_state(event.user_id)
            if state is not None:
                upsert_user_vector_snapshot(event.user_id, state)
        r.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
        logger.info(
            "search event processed entry_id=%s user_id=%s (xack done)",
            msg_id,
            event.user_id,
        )
        return

    if not item_embeddings.get(event.item_id):
        logger.warning(
            "event skipped (unknown item_id) entry_id=%s item_id=%s — xack without embedding update",
            msg_id,
            event.item_id,
        )
        r.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
        return
    # Update user vector
    apply_single_event_to_store(get_user_state(), event.user_id, event, now_ts=time.time())
    _processed_events += 1
    if POSTGRES_ENABLED and SNAPSHOT_EVERY_EVENTS > 0 and (_processed_events % SNAPSHOT_EVERY_EVENTS == 0):
        state = get_user_vector_state(event.user_id)
        if state is not None:
            upsert_user_vector_snapshot(event.user_id, state)
    r.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
    logger.info(
        "event processed entry_id=%s user_id=%s item_id=%s (xack done)",
        msg_id,
        event.user_id,
        event.item_id,
    )


def _restore_user_state_from_snapshots() -> None:
    if not POSTGRES_ENABLED:
        return
    restored = 0
    for user_id, state in list_recent_user_vector_snapshots(limit=RECOVERY_SNAPSHOT_LIMIT):
        if get_user_vector_state(user_id) is not None:
            continue
        save_user_vector_state(user_id, state)
        restored += 1
    if restored > 0:
        logger.info("worker recovery restored user states from postgres snapshots count=%s", restored)


def _log_worker_metrics(r: Redis) -> None:
    global _last_metrics_log_ts
    now = time.time()
    if now - _last_metrics_log_ts < METRICS_LOG_INTERVAL_SECONDS:
        return
    _last_metrics_log_ts = now
    try:
        groups = r.xinfo_groups(STREAM_KEY)
        group_row = next((g for g in groups if g.get("name") == CONSUMER_GROUP), None)
        pending = int(group_row.get("pending", 0)) if group_row else 0
        consumers = int(group_row.get("consumers", 0)) if group_row else 0
        logger.info(
            "worker metrics stream=%s group=%s pending=%s consumers=%s processed_events=%s",
            STREAM_KEY,
            CONSUMER_GROUP,
            pending,
            consumers,
            _processed_events,
        )
    except Exception as exc:
        logger.warning("worker metrics collection failed: %s", exc)


async def run_worker() -> None:
    _configure_logging()
    r = get_redis_client()
    init_group(r)
    ensure_postgres_schema()
    _restore_user_state_from_snapshots()

    logger.info(
        "worker started stream=%s group=%s consumer=%s",
        STREAM_KEY,
        CONSUMER_GROUP,
        CONSUMER,
    )

    while True:
        try:
            resp = r.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER,
                {STREAM_KEY: ">"},
                count=10,
                block=5000,
            )

            if not resp:
                _log_worker_metrics(r)
                continue

            for _, messages in resp:
                for msg_id, data in messages:
                    await process_event(r, msg_id, data)
            _log_worker_metrics(r)

        except Exception as exc:
            logger.exception("worker loop error: %s", exc)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_worker())
