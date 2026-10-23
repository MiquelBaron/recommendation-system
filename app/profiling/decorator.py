from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import Request

from app.profiling.cprofile_util import format_cprofile, maybe_cprofile
from app.profiling.stages import get_current_profile, set_current_profile, stage

F = TypeVar("F", bound=Callable[..., Any])


def bind_profile(request: Request) -> None:
    """FastAPI dependency: re-attach profile in the sync worker thread."""
    profile = getattr(request.state, "profile", None)
    if profile is not None:
        set_current_profile(profile)


def profiled(fn: F) -> F:
    """Wrap a sync endpoint so stages + cProfile run in the handler thread."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        profile = get_current_profile()
        want_cprofile = bool(profile and profile.cprofile_enabled)
        with stage(f"handler.{fn.__name__}"):
            with maybe_cprofile(want_cprofile) as profiler:
                result = fn(*args, **kwargs)
            if profiler is not None and profile is not None:
                profile.cprofile_text = format_cprofile(profiler)
        return result

    return wrapper  # type: ignore[return-value]
