from app.ml.similarity import cosine_similarity
from app.models.schemas import RecommendationItemDTO, RecommendationResponse
from app.storage.catalog import ITEMS, item_embeddings
from app.storage.user_state import get_user_embedding


def _embedding_dim() -> int:
    if not item_embeddings:
        return 0
    return len(next(iter(item_embeddings.values())))


def recommend(user_id: str) -> list[tuple[str, float]]:
    if not item_embeddings:
        return []

    dim = _embedding_dim()
    user_vec = get_user_embedding(user_id)
    if user_vec is None or len(user_vec) != dim:
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
