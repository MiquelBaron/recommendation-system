"""User events (Redis Stream) and per-user dual vectors (Redis strings).

Redis events: stream ``user:events:stream`` with fields user_id, item_id, event_type, timestamp.
Consumer group ``recommender-group`` is used by the recommendation worker (`XREADGROUP`).
Vectors: JSON per user key ``recommend:user_state:{user_id}`` with short_term, long_term, last_event_ts.
Legacy key ``recommend:embedding:{user_id}`` (single list) is read once for migration then removed on save.
"""
import json
import logging
from collections import Counter
from typing import Protocol, runtime_checkable

from redis.exceptions import ResponseError

from app.models.schemas import Event, UserVectorState
from app.storage.redis_client import get_redis_client

STREAM_KEY = "user:events:stream"
CONSUMER_GROUP = "recommender-group"

logger = logging.getLogger(__name__)


@runtime_checkable
class UserStateStore(Protocol):
    def append_event(self, user_id: str, event: Event) -> None: ...
    def get_all_user_events(self, user_id: str) -> list[Event]: ...
    def list_user_summaries(self) -> list[tuple[str, int]]: ...
    def get_user_vector_state(self, user_id: str) -> UserVectorState | None: ...
    def save_user_vector_state(self, user_id: str, state: UserVectorState) -> None: ...
    def ensure_stream_consumer_group(self) -> None: ...


def _user_state_key(user_id: str) -> str:
    return f"recommend:user_state:{user_id}"


def _legacy_emb_key(user_id: str) -> str:
    return f"recommend:embedding:{user_id}"


def _parse_user_state_payload(raw: str) -> UserVectorState | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return UserVectorState(
            short_term_vector=list(map(float, data)),
            long_term_vector=list(map(float, data)),
            last_event_ts=None,
        )
    if not isinstance(data, dict):
        return None
    short = data.get("short_term_vector") or data.get("short")
    long = data.get("long_term_vector") or data.get("long")
    if not isinstance(short, list) or not isinstance(long, list):
        return None
    last = data.get("last_event_ts")
    last_f: float | None
    if last is None:
        last_f = None
    else:
        try:
            last_f = float(last)
        except (TypeError, ValueError):
            last_f = None
    return UserVectorState(
        short_term_vector=[float(x) for x in short],
        long_term_vector=[float(x) for x in long],
        last_event_ts=last_f,
    )


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
                "query": event.query or "",
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
                    query=fields.get("query") or None,
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

    def get_user_vector_state(self, user_id: str) -> UserVectorState | None:
        raw = self._r.get(_user_state_key(user_id))
        if raw is not None:
            parsed = _parse_user_state_payload(raw)
            if parsed is not None:
                return parsed

        legacy = self._r.get(_legacy_emb_key(user_id))
        if legacy is None:
            return None
        try:
            emb = json.loads(legacy)
        except json.JSONDecodeError:
            return None
        if not isinstance(emb, list):
            return None
        vec = [float(x) for x in emb]
        return UserVectorState(
            short_term_vector=vec,
            long_term_vector=list(vec),
            last_event_ts=None,
        )

    def save_user_vector_state(self, user_id: str, state: UserVectorState) -> None:
        payload = {
            "short_term_vector": state.short_term_vector,
            "long_term_vector": state.long_term_vector,
            "last_event_ts": state.last_event_ts,
        }
        key = _user_state_key(user_id)
        self._r.set(key, json.dumps(payload))
        self._r.delete(_legacy_emb_key(user_id))

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


def get_user_vector_state(user_id: str) -> UserVectorState | None:
    return get_user_state().get_user_vector_state(user_id)


def save_user_vector_state(user_id: str, state: UserVectorState) -> None:
    get_user_state().save_user_vector_state(user_id, state)


def ensure_stream_consumer_group() -> None:
    get_user_state().ensure_stream_consumer_group()
