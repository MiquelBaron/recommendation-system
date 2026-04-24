from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class Event:
    user_id: str
    item_id: str
    event_type: str
    timestamp: float


class EventPayload(BaseModel):
    user_id: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    timestamp: float


class RecommendationItemDTO(BaseModel):
    item_id: str
    item_name: str
    score: float


class RecommendationResponse(BaseModel):
    user_id: str
    recommendations: list[RecommendationItemDTO]


class UserEventDTO(BaseModel):
    item_id: str
    item_name: str
    event_type: str
    timestamp: float


class UserEventsResponse(BaseModel):
    user_id: str
    events: list[UserEventDTO]
    processed_event_count: int


class UserSummaryDTO(BaseModel):
    user_id: str
    event_count: int


class UsersListResponse(BaseModel):
    users: list[UserSummaryDTO]
