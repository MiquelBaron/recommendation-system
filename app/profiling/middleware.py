from __future__ import annotations

import os
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.profiling.stages import (
    RequestProfile,
    new_request_id,
    reset_current_profile,
    set_current_profile,
)
from app.profiling.store import save_profile

PROFILING_ENABLED = os.getenv("PROFILING_ENABLED", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _wants_cprofile(request: Request) -> bool:
    if request.query_params.get("profile") == "1":
        return True
    header = request.headers.get("x-profile", "").strip().lower()
    return header in {"1", "true", "yes", "on"}


def _should_skip(path: str) -> bool:
    return path.startswith("/profiling/static")


class ProfilingMiddleware(BaseHTTPMiddleware):
    """Create a per-request profile shell, measure wall time, persist results.

    cProfile runs in the endpoint thread via ``profiled`` (see ``decorator.py``),
    because FastAPI sync handlers execute in a worker thread.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not PROFILING_ENABLED or _should_skip(request.url.path):
            return await call_next(request)

        profile = RequestProfile(
            request_id=new_request_id(),
            method=request.method,
            path=request.url.path,
            query=str(request.url.query or ""),
            cprofile_enabled=_wants_cprofile(request),
        )
        request.state.profile = profile
        token = set_current_profile(profile)
        wall_start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            profile.status_code = 500
            profile.total_ms = (time.perf_counter() - wall_start) * 1000.0
            save_profile(profile)
            raise
        finally:
            reset_current_profile(token)

        profile.status_code = response.status_code
        profile.total_ms = (time.perf_counter() - wall_start) * 1000.0
        save_profile(profile)
        response.headers["X-Profile-Id"] = profile.request_id
        if profile.cprofile_enabled:
            response.headers["X-Profile-CProfile"] = (
                "1" if profile.cprofile_text else "requested"
            )
        return response
