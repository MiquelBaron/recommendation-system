"""User events (Redis Stream) and per-user embedding vectors (Redis strings).

Redis events: stream ``user:events:stream`` with fields user_id, item_id, event_type, timestamp.
Consumer group ``recommender-group`` is used by the recommendation worker (`XREADGROUP`).
Embeddings: JSON per user key ``recommend:embedding:{user_id}``.
"""
import json
import logging
from collections import Counter
from typing import Protocol, runtime_checkable

from redis.exceptions import ResponseError

from app.models.schemas import Event
from app.storage.redis_client import get_redis_client

STREAM_KEY = "user:events:stream"
CONSUMER_GROUP = "recommender-group"

logger = logging.getLogger(__name__)


@runtime_checkable
class UserStateStore(Protocol):
    def append_event(self, user_id: str, event: Event) -> None: ...
    def get_all_user_events(self, user_id: str) -> list[Event]: ...
    def list_user_summaries(self) -> list[tuple[str, int]]: ...
    def get_user_embedding(self, user_id: str) -> list[float] | None: ...
    def save_user_embedding(self, user_id: str, embedding: list[float]) -> None: ...
    def ensure_stream_consumer_group(self) -> None: ...


def _emb_key(user_id: str) -> str:
    return f"recommend:embedding:{user_id}"


class RedisUserStateStore:
    def __init__(self) -> None:
        self._r = get_redis_client()
        self.ensure_stream_consumer_group()

    def append_event(self, user_id: str, event: Event) -> None:
        entry_id = self._r.xadd(
            STREAM_KEY,
            {
                "user_id": user_id,
                "item_id": event.item_id,
                "event_type": event.event_type,
                "timestamp": str(event.timestamp),
            },
        )
        logger.info(
            "event queued stream=%s entry_id=%s user_id=%s item_id=%s event_type=%s timestamp=%s",
            STREAM_KEY,
            entry_id,
            user_id,
            event.item_id,
            event.event_type,
            event.timestamp,
        )

    def get_all_user_events(self, user_id: str) -> list[Event]:
        entries = self._r.xrange(STREAM_KEY, "-", "+")
        events: list[Event] = []
        for _entry_id, fields in entries:
            if fields.get("user_id") != user_id:
                continue
            events.append(
                Event(
                    user_id=fields["user_id"],
                    item_id=fields["item_id"],
                    event_type=fields["event_type"],
                    timestamp=float(fields["timestamp"]),
                )
            )
        return sorted(events, key=lambda e: (e.timestamp, e.item_id, e.event_type))

    def list_user_summaries(self) -> list[tuple[str, int]]:
        entries = self._r.xrange(STREAM_KEY, "-", "+")
        counts: Counter[str] = Counter()
        for _entry_id, fields in entries:
            uid = fields.get("user_id")
            if uid:
                counts[uid] += 1
        return [(user_id, counts[user_id]) for user_id in sorted(counts)]

    def get_user_embedding(self, user_id: str) -> list[float] | None:
        raw = self._r.get(_emb_key(user_id))
        if raw is None:
            return None
        return json.loads(raw)

    def save_user_embedding(self, user_id: str, embedding: list[float]) -> None:
        self._r.set(_emb_key(user_id), json.dumps(embedding))

    def ensure_stream_consumer_group(self) -> None:
        try:
            self._r.xgroup_create(
                STREAM_KEY,
                CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                return
            raise


_store: RedisUserStateStore | None = None


def get_user_state() -> RedisUserStateStore:
    global _store
    if _store is None:
        _store = RedisUserStateStore()
    return _store


def append_event(user_id: str, event: Event) -> None:
    get_user_state().append_event(user_id, event)


def get_all_user_events(user_id: str) -> list[Event]:
    return get_user_state().get_all_user_events(user_id)


def list_user_summaries() -> list[tuple[str, int]]:
    return get_user_state().list_user_summaries()


def get_user_embedding(user_id: str) -> list[float] | None:
    return get_user_state().get_user_embedding(user_id)


def save_user_embedding(user_id: str, embedding: list[float]) -> None:
    get_user_state().save_user_embedding(user_id, embedding)


def ensure_stream_consumer_group() -> None:
    get_user_state().ensure_stream_consumer_group()
