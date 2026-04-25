"""Incremental dual user vectors: one stream event updates short- and long-term branches.

Does not scan full event history; the Redis stream is the append-only log for inspection.
"""

import logging
import math
import os
import time

from app.ml.embeddings import (
    LONG_TERM_DECAY_LAMBDA,
    SHORT_TERM_DECAY_LAMBDA,
    embed_text,
    event_embedding_weight,
    l2_normalize,
    time_decay_multiplier,
)
from app.ml.similarity import cosine_similarity
from app.models.schemas import Event, UserVectorState
from app.storage.catalog import item_embeddings
from app.storage.user_state import UserStateStore

logger = logging.getLogger(__name__)

SEARCH_TOP_K = int(os.getenv("SEARCH_TOP_K", "7"))
SEARCH_QUERY_ALPHA = float(os.getenv("SEARCH_QUERY_ALPHA", "2.5"))
SEARCH_ITEM_BETA = float(os.getenv("SEARCH_ITEM_BETA", "1.0"))
SEARCH_LONG_TERM_SCALE = float(os.getenv("SEARCH_LONG_TERM_SCALE", "0.35"))
SEARCH_SIMILARITY_THRESHOLD = float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", "0.5"))
SHORT_TERM_DISLIKE_MULTIPLIER = float(os.getenv("SHORT_TERM_DISLIKE_MULTIPLIER", "2.0"))


def _embedding_dim() -> int:
    if not item_embeddings:
        return 0
    return len(next(iter(item_embeddings.values())))


def _load_or_init_user_vectors(
    store: UserStateStore,
    user_id: str,
    dim: int,
) -> tuple[list[float], list[float], UserVectorState | None, bool]:
    prior = store.get_user_vector_state(user_id)
    if prior is None:
        return [0.0] * dim, [0.0] * dim, None, False
    short_old = (
        list(prior.short_term_vector)
        if len(prior.short_term_vector) == dim
        else [0.0] * dim
    )
    long_old = (
        list(prior.long_term_vector)
        if len(prior.long_term_vector) == dim
        else [0.0] * dim
    )
    return short_old, long_old, prior, True


def _update_last_ts(prior: UserVectorState | None, event_ts: float) -> float:
    if prior is None or prior.last_event_ts is None:
        return event_ts
    return max(prior.last_event_ts, event_ts)


def _top_k_by_query_embedding(
    query_embedding: list[float],
    *,
    top_k: int,
    min_similarity: float | None = None,
) -> list[tuple[str, float, list[float]]]:
    scored: list[tuple[str, float, list[float]]] = []
    threshold = min_similarity if min_similarity is not None else float("-inf")
    for item_id, item_vec in item_embeddings.items():
        score = cosine_similarity(query_embedding, item_vec)
        if score >= threshold:
            scored.append((item_id, score, item_vec))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:max(0, top_k)]


def _weighted_item_sum(top_items: list[tuple[str, float, list[float]]], dim: int) -> list[float]:
    if not top_items:
        return [0.0] * dim
    score_sum = sum(score for _item_id, score, _vec in top_items)
    if score_sum <= 0:
        return [0.0] * dim
    acc = [0.0] * dim
    for _item_id, score, vec in top_items:
        w = score / score_sum
        for i in range(dim):
            acc[i] += w * vec[i]
    return acc


def _apply_search_event_to_store(
    store: UserStateStore,
    user_id: str,
    event: Event,
    *,
    now_ts: float,
) -> None:
    dim = _embedding_dim()
    if dim == 0:
        logger.warning("search event skip: no item embeddings user_id=%s", user_id)
        return
    if not event.query:
        logger.warning(
            "search event skip: empty query user_id=%s item_id=%s timestamp=%s",
            user_id,
            event.item_id,
            event.timestamp,
        )
        return

    logger.info("query embedding start user_id=%s query=%s", user_id, event.query)

    # Query vector
    query_vec = embed_text(event.query)
    if len(query_vec) != dim:
        logger.warning(
            "search event skip: query embedding dim mismatch user_id=%s query_dim=%s item_dim=%s",
            user_id,
            len(query_vec),
            dim,
        )
        return
    logger.info("query embedded user_id=%s dim=%s", user_id, len(query_vec))

    top_items = _top_k_by_query_embedding(
        query_vec,
        top_k=SEARCH_TOP_K,
        min_similarity=SEARCH_SIMILARITY_THRESHOLD,
    )
    if not top_items:
        # Fallback to top-K without threshold to keep some search signal.
        top_items = _top_k_by_query_embedding(query_vec, top_k=SEARCH_TOP_K)
        logger.info(
            "search topK threshold fallback user_id=%s threshold=%.3f",
            user_id,
            SEARCH_SIMILARITY_THRESHOLD,
        )
    logger.info(
        "topK items retrieved user_id=%s k=%s items=%s",
        user_id,
        len(top_items),
        [item_id for item_id, _score, _ in top_items],
    )
    weighted_items = _weighted_item_sum(top_items, dim)
    short_decay = time_decay_multiplier(
        event.timestamp,
        now_ts,
        decay_lambda=SHORT_TERM_DECAY_LAMBDA,
    )
    long_decay = time_decay_multiplier(
        event.timestamp,
        now_ts,
        decay_lambda=LONG_TERM_DECAY_LAMBDA,
    )

    short_old, long_old, prior, had_prior = _load_or_init_user_vectors(store, user_id, dim)
    short_raw = [
        short_decay * short_old[i]
        + SEARCH_QUERY_ALPHA * query_vec[i]
        + SEARCH_ITEM_BETA * weighted_items[i]
        for i in range(dim)
    ]
    long_raw = [
        long_decay * long_old[i]
        + (SEARCH_QUERY_ALPHA * SEARCH_LONG_TERM_SCALE) * query_vec[i]
        + (SEARCH_ITEM_BETA * SEARCH_LONG_TERM_SCALE) * weighted_items[i]
        for i in range(dim)
    ]
    short_new = l2_normalize(short_raw)
    long_new = l2_normalize(long_raw)
    last_ts = _update_last_ts(prior, event.timestamp)
    store.save_user_vector_state(
        user_id,
        UserVectorState(
            short_term_vector=short_new,
            long_term_vector=long_new,
            last_event_ts=last_ts,
        ),
    )
    logger.info(
        "user vector updated from search event user_id=%s had_prior=%s query=%s dim=%s",
        user_id,
        had_prior,
        event.query,
        dim,
    )


def apply_single_event_to_store(
    store: UserStateStore,
    user_id: str,
    event: Event,
    *,
    now_ts: float | None = None,
) -> None:
    """Apply one event to short_term_vector and long_term_vector (separate decay), update last_event_ts.

    Per-event updates are kept in raw accumulated space. L2 normalization is applied only at retrieval time.
    """
    if now_ts is None:
        now_ts = time.time()

    if event.event_type == "search":
        _apply_search_event_to_store(store, user_id, event, now_ts=now_ts)
        return

    dim = _embedding_dim()
    if dim == 0:
        logger.warning(
            "user vectors skip: no item_embeddings dim user_id=%s item_id=%s",
            user_id,
            event.item_id,
        )
        return

    # Fetch item vector
    item_vector = item_embeddings.get(event.item_id)
    if not item_vector:
        logger.warning(
            "user vectors skip: unknown item_id=%s user_id=%s event_type=%s",
            event.item_id,
            user_id,
            event.event_type,
        )
        return
    # Fetch user vector
    short_old, long_old, prior, had_prior = _load_or_init_user_vectors(store, user_id, dim)

    #Calculate event weights for short and long term vectors

    weight_s = event_embedding_weight(
        event.event_type,
        event.timestamp,
        now_ts,
        decay_lambda=SHORT_TERM_DECAY_LAMBDA,
    )
    if event.event_type == "dislike":
        weight_s *= SHORT_TERM_DISLIKE_MULTIPLIER

    weight_l = event_embedding_weight(
        event.event_type,
        event.timestamp,
        now_ts,
        decay_lambda=LONG_TERM_DECAY_LAMBDA,
    )
    delta_s = [weight_s * value for value in item_vector]
    delta_l = [weight_l * value for value in item_vector]
    short_new = [short_old[i] + delta_s[i] for i in range(dim)]
    long_new = [long_old[i] + delta_l[i] for i in range(dim)]

    last_ts = _update_last_ts(prior, event.timestamp)

    store.save_user_vector_state(
        user_id,
        UserVectorState(
            short_term_vector=short_new,
            long_term_vector=long_new,
            last_event_ts=last_ts,
        ),
    )

    l2_s = math.sqrt(sum(x * x for x in short_new))
    l2_l = math.sqrt(sum(x * x for x in long_new))
    logger.info(
        "dual vectors updated user_id=%s item_id=%s event_type=%s weight_short=%.6f weight_long=%.6f "
        "had_prior=%s raw_norm_short=%.6f raw_norm_long=%.6f dim=%s last_event_ts=%s",
        user_id,
        event.item_id,
        event.event_type,
        weight_s,
        weight_l,
        had_prior,
        l2_s,
        l2_l,
        dim,
        last_ts,
    )
