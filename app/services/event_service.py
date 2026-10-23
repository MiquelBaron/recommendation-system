from app.models.schemas import (
    Event,
    EventPayload,
    UserEventDTO,
    UserEventsResponse,
    UserSummaryDTO,
    UsersListResponse,
)
from app.profiling.stages import stage
from app.storage.postgres_store import insert_event_durable
from app.storage.catalog import ITEMS
from app.storage.user_state import append_event, get_all_user_events, list_user_summaries


def register_event(payload: EventPayload) -> None:
    with stage("events.build_model"):
        event = Event(
            user_id=payload.user_id,
            item_id=payload.item_id,
            event_type=payload.event_type,
            timestamp=payload.timestamp,
            query=payload.query,
        )
    # Durable write first (PostgreSQL), then enqueue for async processing.
    with stage("events.postgres_insert"):
        insert_event_durable(event, source="api")
    with stage("events.redis_stream_xadd"):
        append_event(event.user_id, event)


def list_users() -> UsersListResponse:
    with stage("users.list_from_stream"):
        rows = list_user_summaries()
    with stage("users.build_response"):
        return UsersListResponse(
            users=[
                UserSummaryDTO(user_id=user_id, event_count=count)
                for user_id, count in rows
            ]
        )


def get_user_events(user_id: str) -> UserEventsResponse:
    with stage("users.load_events"):
        events = get_all_user_events(user_id)
    with stage("users.build_events_response"):
        return UserEventsResponse(
            user_id=user_id,
            events=[
                UserEventDTO(
                    item_id=e.item_id,
                    item_name=ITEMS.get(e.item_id, ""),
                    event_type=e.event_type,
                    timestamp=e.timestamp,
                    query=e.query,
                )
                for e in events
            ],
            processed_event_count=len(events),
        )
