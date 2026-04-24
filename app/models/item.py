from pydantic import BaseModel, Field


class Item(BaseModel):
    id: str
    title: str
    genres: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    year: int
    duration: int
