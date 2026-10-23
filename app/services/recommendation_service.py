import time

from app.ml.embeddings import combined_user_vector_for_retrieval
from app.ml.similarity import cosine_similarity
from app.models.schemas import RecommendationItemDTO, RecommendationResponse
from app.profiling.stages import stage
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
    with stage("recommend.load_user_state"):
        state = get_user_vector_state(user_id)
    now_ts = time.time()
    with stage("recommend.blend_user_vector"):
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

    with stage("recommend.cosine_score_all_items"):
        scores: list[tuple[str, float]] = []
        for item_id, item_vec in item_embeddings.items():
            score = cosine_similarity(user_vec, item_vec)
            scores.append((item_id, score))
        return sorted(scores, key=lambda value: value[1], reverse=True)


def get_recommendations(user_id: str) -> RecommendationResponse:
    with stage("recommend.rank"):
        ranked_pairs = recommend(user_id)
    with stage("recommend.build_response"):
        ranked = [
            RecommendationItemDTO(
                item_id=item_id,
                item_name=ITEMS.get(item_id, ""),
                score=score,
            )
            for item_id, score in ranked_pairs
        ]
        return RecommendationResponse(user_id=user_id, recommendations=ranked)
