"""Incremental user embedding: one event → delta on persisted vector, then L2 normalize.

Does not scan full event history; the Redis stream is the append-only log for inspection.
"""

import logging
import math
import time

from app.ml.embeddings import event_embedding_weight, l2_normalize
from app.models.schemas import Event
from app.storage.catalog import item_embeddings
from app.storage.user_state import UserStateStore

logger = logging.getLogger(__name__)


def _embedding_dim() -> int:
    if not item_embeddings:
        return 0
    return len(next(iter(item_embeddings.values())))


def apply_single_event_to_store(
    store: UserStateStore,
    user_id: str,
    event: Event,
    *,
    now_ts: float | None = None,
) -> None:
    """user_embedding_new = normalize(user_embedding_old + item_embedding * weight(event))."""
    dim = _embedding_dim()
    if dim == 0:
        logger.warning(
            "user embedding skip: no item_embeddings dim user_id=%s item_id=%s",
            user_id,
            event.item_id,
        )
        return

    if now_ts is None:
        now_ts = time.time()

    item_vector = item_embeddings.get(event.item_id)
    if not item_vector:
        logger.warning(
            "user embedding skip: unknown item_id=%s user_id=%s event_type=%s",
            event.item_id,
            user_id,
            event.event_type,
        )
        return

    old = store.get_user_embedding(user_id)
    old_vec = list(old) if old else [0.0] * dim
    had_prior = old is not None

    weight = event_embedding_weight(event.event_type, event.timestamp, now_ts)
    delta = [weight * value for value in item_vector]
    new_raw = [old_vec[i] + delta[i] for i in range(dim)]
    new_emb = l2_normalize(new_raw)
    store.save_user_embedding(user_id, new_emb)

    l2_norm = math.sqrt(sum(x * x for x in new_emb))
    logger.info(
        "vector updated user_id=%s item_id=%s event_type=%s weight=%.6f had_prior_embedding=%s "
        "new_l2_norm=%.6f dim=%s",
        user_id,
        event.item_id,
        event.event_type,
        weight,
        had_prior,
        l2_norm,
        dim,
    )
