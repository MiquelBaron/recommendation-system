from fastapi import APIRouter

from app.models.schemas import (
    EventPayload,
    RecommendationResponse,
    UserEventsResponse,
    UsersListResponse,
)
from app.services.event_service import get_user_events, list_users, register_event
from app.services.recommendation_service import get_recommendations


router = APIRouter(prefix="/api", tags=["api"])


@router.post("/events")
def create_event(payload: EventPayload) -> dict[str, str]:
    register_event(payload)
    return {"status": "event queued"}


@router.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def recommendations(user_id: str) -> RecommendationResponse:
    return get_recommendations(user_id)


@router.get("/users", response_model=UsersListResponse)
def list_all_users() -> UsersListResponse:
    return list_users()


@router.get("/users/{user_id}/events", response_model=UserEventsResponse)
def list_user_events(user_id: str) -> UserEventsResponse:
    return get_user_events(user_id)
