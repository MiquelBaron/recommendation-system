from fastapi import APIRouter

from app.models.schemas import EventPayload, RecommendationResponse
from app.services.event_service import register_event
from app.services.recommendation_service import get_recommendations


router = APIRouter(prefix="/api", tags=["api"])


@router.post("/events")
def create_event(payload: EventPayload) -> dict[str, str]:
    register_event(payload)
    return {"message": "event registered"}


@router.get("/recommendations/{user_id}", response_model=RecommendationResponse)
def recommendations(user_id: str) -> RecommendationResponse:
    return get_recommendations(user_id)
