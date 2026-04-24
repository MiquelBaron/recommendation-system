import asyncio
import logging
import time

from redis import Redis

from app.models.schemas import Event
from app.services.user_embedding_service import apply_single_event_to_store
from app.storage.catalog import item_embeddings
from app.storage.redis_client import get_redis_client
from app.storage.user_state import CONSUMER_GROUP, STREAM_KEY, get_user_state

logger = logging.getLogger(__name__)

CONSUMER = "worker-1"


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
    event = Event(
        user_id=data["user_id"],
        item_id=data["item_id"],
        event_type=data["event_type"],
        timestamp=float(data["timestamp"]),
    )
    logger.info(
        "event received entry_id=%s user_id=%s item_id=%s event_type=%s timestamp=%s",
        msg_id,
        event.user_id,
        event.item_id,
        event.event_type,
        event.timestamp,
    )
    if not item_embeddings.get(event.item_id):
        logger.warning(
            "event skipped (unknown item_id) entry_id=%s item_id=%s — xack without embedding update",
            msg_id,
            event.item_id,
        )
        r.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
        return
    apply_single_event_to_store(get_user_state(), event.user_id, event, now_ts=time.time())
    r.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)
    logger.info(
        "event processed entry_id=%s user_id=%s item_id=%s (xack done)",
        msg_id,
        event.user_id,
        event.item_id,
    )


async def run_worker() -> None:
    _configure_logging()
    r = get_redis_client()
    init_group(r)

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
                continue

            for _, messages in resp:
                for msg_id, data in messages:
                    await process_event(r, msg_id, data)

        except Exception as exc:
            logger.exception("worker loop error: %s", exc)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_worker())
