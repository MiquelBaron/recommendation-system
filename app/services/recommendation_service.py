import time

from app.ml.embeddings import combined_user_vector_for_retrieval
from app.ml.similarity import cosine_similarity
from app.models.schemas import RecommendationItemDTO, RecommendationResponse
from app.storage.catalog import ITEMS, item_embeddings
from app.storage.user_state import get_user_vector_state


def _embedding_dim() -> int:
    if not item_embeddings:
        return 0
    return len(next(iter(item_embeddings.values())))


def recommend(user_id: str) -> list[tuple[str, float]]:
    if not item_embeddings:
        return []

    dim = _embedding_dim()
    state = get_user_vector_state(user_id)
    now_ts = time.time()
    if state is None:
        user_vec = [0.0] * dim
    else:
        user_vec = combined_user_vector_for_retrieval(
            state.short_term_vector,
            state.long_term_vector,
            state.last_event_ts,
            now_ts,
        )
        if not user_vec or len(user_vec) != dim:
            user_vec = [0.0] * dim

    scores: list[tuple[str, float]] = []
    for item_id, item_vec in item_embeddings.items():
        score = cosine_similarity(user_vec, item_vec)
        scores.append((item_id, score))
    return sorted(scores, key=lambda value: value[1], reverse=True)


def get_recommendations(user_id: str) -> RecommendationResponse:
    ranked = [
        RecommendationItemDTO(
            item_id=item_id,
            item_name=ITEMS.get(item_id, ""),
            score=score,
        )
        for item_id, score in recommend(user_id)
    ]
    return RecommendationResponse(user_id=user_id, recommendations=ranked)
