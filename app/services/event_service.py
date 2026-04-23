from app.models.schemas import EventPayload
from app.storage.redis_client import get_redis_client


def register_event(payload: EventPayload) -> None:
    redis = get_redis_client()
    key = f"user:{payload.user_id}:events"
    redis.rpush(key, payload.model_dump_json())
