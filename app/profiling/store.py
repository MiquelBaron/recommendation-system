from __future__ import annotations

import os
import threading
from collections import deque
from typing import Deque, Optional

from app.profiling.stages import RequestProfile

_MAX_PROFILES = int(os.getenv("PROFILING_MAX_PROFILES", "100"))
_lock = threading.Lock()
_profiles: Deque[RequestProfile] = deque(maxlen=max(1, _MAX_PROFILES))


def save_profile(profile: RequestProfile) -> None:
    with _lock:
        _profiles.appendleft(profile)


def list_profiles(limit: int = 50) -> list[RequestProfile]:
    with _lock:
        return list(_profiles)[: max(1, limit)]


def get_profile(request_id: str) -> Optional[RequestProfile]:
    with _lock:
        for profile in _profiles:
            if profile.request_id == request_id:
                return profile
    return None


def clear_profiles() -> None:
    with _lock:
        _profiles.clear()
