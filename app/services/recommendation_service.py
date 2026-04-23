from app.ml.embeddings import embed_text
from app.ml.similarity import cosine_similarity
from app.models.schemas import RecommendationItem, RecommendationResponse


def get_recommendations(user_id: str) -> RecommendationResponse:
    # Placeholder logic that can be replaced with your model pipeline.
    user_vector = embed_text(user_id)
    candidate_ids = ["item-1", "item-2", "item-3"]
    ranked = sorted(
        (
            RecommendationItem(
                item_id=item_id,
                score=cosine_similarity(user_vector, embed_text(item_id)),
            )
            for item_id in candidate_ids
        ),
        key=lambda item: item.score,
        reverse=True,
    )
    return RecommendationResponse(user_id=user_id, recommendations=ranked)
