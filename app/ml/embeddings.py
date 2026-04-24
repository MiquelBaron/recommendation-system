import math
import os

from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")

# Exponential time decay: multiplier = exp(-lambda * time_diff) where time_diff is in the unit below.
# Tune lambda in ~0.01–0.1 for hours, or smaller if using days.
DEFAULT_TIME_DECAY_LAMBDA = float(os.getenv("EMBEDDING_TIME_DECAY_LAMBDA", "0.05"))
# "hours" (default) or "days" — must match how you interpret EMBEDDING_TIME_DECAY_LAMBDA.
_TIME_DECAY_UNIT = os.getenv("EMBEDDING_TIME_DECAY_UNIT", "hours").strip().lower()

EVENT_WEIGHTS = {
    "impression": 0.1,
    "click": 0.5,
    "watch": 2.0,
    "like": 3.0,
    "dislike": -2.0,
}


def embed_text(text: str) -> list[float]:
    embedding = _model.encode(text)
    return embedding.tolist()


def l2_normalize(vector: list[float]) -> list[float]:
    if not vector:
        return vector
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return [0.0] * len(vector)
    return [x / norm for x in vector]


def _time_diff_in_decay_unit(event_ts: float, now_ts: float) -> float:
    seconds = max(0.0, now_ts - event_ts)
    if _TIME_DECAY_UNIT in ("day", "days", "d"):
        return seconds / 86400.0
    return seconds / 3600.0


def time_decay_multiplier(
    event_ts: float,
    now_ts: float,
    *,
    decay_lambda: float | None = None,
) -> float:
    lam = DEFAULT_TIME_DECAY_LAMBDA if decay_lambda is None else decay_lambda
    t = _time_diff_in_decay_unit(event_ts, now_ts)
    return math.exp(-lam * t)


def event_embedding_weight(
    event_type: str,
    event_ts: float,
    now_ts: float,
    *,
    decay_lambda: float | None = None,
) -> float:
    base = EVENT_WEIGHTS.get(event_type, 0.0)
    return base * time_decay_multiplier(event_ts, now_ts, decay_lambda=decay_lambda)
