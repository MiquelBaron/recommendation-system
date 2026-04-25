from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator


@dataclass
class Event:
    user_id: str
    item_id: str
    event_type: str
    timestamp: float
    query: str | None = None


@dataclass
class UserVectorState:
    """Per-user dual vectors (streaming-updated) + timestamp of last applied event for recency blend."""

    short_term_vector: list[float]
    long_term_vector: list[float]
    last_event_ts: float | None


class EventPayload(BaseModel):
    user_id: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    event_type: Literal["impression", "click", "watch", "like", "dislike", "search"]
    timestamp: float
    query: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_search_query(self) -> "EventPayload":
        if self.event_type == "search" and not self.query:
            raise ValueError("query is required when event_type is 'search'")
        return self


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
    query: str | None = None


class UserEventsResponse(BaseModel):
    user_id: str
    events: list[UserEventDTO]
    processed_event_count: int


class UserSummaryDTO(BaseModel):
    user_id: str
    event_count: int


class UsersListResponse(BaseModel):
    users: list[UserSummaryDTO]
