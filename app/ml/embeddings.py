import math
import os

from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")

# Exponential time decay: multiplier = exp(-lambda * time_diff) where time_diff is in the unit below.
# Tune lambda in ~0.01–0.1 for hours, or smaller if using days.
DEFAULT_TIME_DECAY_LAMBDA = float(os.getenv("EMBEDDING_TIME_DECAY_LAMBDA", "0.05"))
# Short-term branch: stronger decay (recent intent fades faster in the delta weight).
SHORT_TERM_DECAY_LAMBDA = float(
    os.getenv("EMBEDDING_SHORT_DECAY_LAMBDA", str(DEFAULT_TIME_DECAY_LAMBDA * 2.5))
)
# Long-term branch: softer decay (stable preferences).
LONG_TERM_DECAY_LAMBDA = float(
    os.getenv("EMBEDDING_LONG_DECAY_LAMBDA", str(DEFAULT_TIME_DECAY_LAMBDA * 0.35))
)
# Blend user_vector = alpha * short + (1-alpha) * long; alpha high when last event is recent.
RECENCY_ALPHA_MIN = float(os.getenv("RECENCY_ALPHA_MIN", "0.15"))
RECENCY_ALPHA_MAX = float(os.getenv("RECENCY_ALPHA_MAX", "0.85"))
RECENCY_ALPHA_HALFLIFE_HOURS = float(os.getenv("RECENCY_ALPHA_HALFLIFE_HOURS", "24"))
# "hours" (default) or "days" — must match how you interpret decay lambdas.
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


def _hours_since_last_event(last_event_ts: float, now_ts: float) -> float:
    seconds = max(0.0, now_ts - last_event_ts)
    return seconds / 3600.0


def recency_alpha(last_event_ts: float | None, now_ts: float) -> float:
    """Higher when the last interaction was recent (more weight on short_term_vector)."""
    if last_event_ts is None:
        return RECENCY_ALPHA_MIN
    h = _hours_since_last_event(last_event_ts, now_ts)
    # exp(-h / T): h=0 -> 1; h=T -> ~0.37 toward min
    span = RECENCY_ALPHA_MAX - RECENCY_ALPHA_MIN
    if RECENCY_ALPHA_HALFLIFE_HOURS <= 0:
        return RECENCY_ALPHA_MAX if h == 0 else RECENCY_ALPHA_MIN
    return RECENCY_ALPHA_MIN + span * math.exp(-h / RECENCY_ALPHA_HALFLIFE_HOURS)


def combined_user_vector_for_retrieval(
    short_term: list[float],
    long_term: list[float],
    last_event_ts: float | None,
    now_ts: float,
) -> list[float]:
    """Linear blend by recency, then L2-normalize for cosine similarity."""
    dim = max(len(short_term), len(long_term))
    if dim == 0:
        return []
    s = short_term if len(short_term) == dim else list(short_term) + [0.0] * (dim - len(short_term))
    l = long_term if len(long_term) == dim else list(long_term) + [0.0] * (dim - len(long_term))
    a = recency_alpha(last_event_ts, now_ts)
    raw = [a * s[i] + (1.0 - a) * l[i] for i in range(dim)]
    return l2_normalize(raw)
