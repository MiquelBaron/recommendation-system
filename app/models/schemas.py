from pydantic import BaseModel, Field


class EventPayload(BaseModel):
    user_id: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    timestamp: str | None = None


class RecommendationItem(BaseModel):
    item_id: str
    score: float


class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: list[RecommendationItem]
