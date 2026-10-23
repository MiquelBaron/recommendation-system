from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator, Optional


@dataclass
class StageRecord:
    name: str
    duration_ms: float


@dataclass
class RequestProfile:
    request_id: str
    method: str
    path: str
    query: str = ""
    status_code: int = 0
    started_at: float = field(default_factory=time.time)
    total_ms: float = 0.0
    stages: list[StageRecord] = field(default_factory=list)
    cprofile_text: Optional[str] = None
    cprofile_enabled: bool = False

    def add_stage(self, name: str, duration_ms: float) -> None:
        self.stages.append(StageRecord(name=name, duration_ms=duration_ms))


_current_profile: ContextVar[Optional[RequestProfile]] = ContextVar(
    "request_profile", default=None
)


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def get_current_profile() -> Optional[RequestProfile]:
    return _current_profile.get()


def set_current_profile(profile: Optional[RequestProfile]):
    return _current_profile.set(profile)


def reset_current_profile(token) -> None:
    _current_profile.reset(token)


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Record wall-clock time for a named stage when a request profile is active."""
    profile = _current_profile.get()
    if profile is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        profile.add_stage(name, (time.perf_counter() - start) * 1000.0)
