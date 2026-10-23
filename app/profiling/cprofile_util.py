from __future__ import annotations

import cProfile
import io
import pstats
from contextlib import contextmanager
from typing import Iterator, Optional


@contextmanager
def maybe_cprofile(enabled: bool) -> Iterator[Optional[cProfile.Profile]]:
    if not enabled:
        yield None
        return
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        yield profiler
    finally:
        profiler.disable()


def format_cprofile(profiler: cProfile.Profile, limit: int = 40) -> str:
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs()
    stats.sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(limit)
    return stream.getvalue()
