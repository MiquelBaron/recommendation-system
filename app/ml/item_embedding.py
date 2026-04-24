"""Structured item → dense vector (same dim as sentence-transformer) for cosine similarity."""

from app.ml.embeddings import embed_text, l2_normalize
from app.models.item import Item

_WEIGHT_TITLE = 0.42
_WEIGHT_GENRES = 0.28
_WEIGHT_TAGS = 0.22


def _normalize_int(value: int, low: int, high: int) -> float:
    if high <= low:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _genres_sentence(item: Item) -> str:
    if not item.genres:
        return "unknown genre"
    return ", ".join(item.genres)


def _tags_sentence(item: Item) -> str:
    if not item.tags:
        return "unknown tag"
    return ", ".join(item.tags)


def item_to_embedding(
    item: Item,
    *,
    year_bounds: tuple[int, int],
    duration_bounds: tuple[int, int],
) -> list[float]:
    """Build one vector per item: per-field ST embeddings + weighted fusion + numeric bias, L2-normalized."""
    y_min, y_max = year_bounds
    d_min, d_max = duration_bounds

    e_title = embed_text(item.title)
    e_genres = embed_text(_genres_sentence(item))
    e_tags = embed_text(_tags_sentence(item))

    ny = _normalize_int(item.year, y_min, y_max)
    nd = _normalize_int(item.duration, d_min, d_max)
    numeric_bias = [ny * 0.1, nd * 0.1]

    dim = len(e_title)
    combined: list[float] = []
    for i in range(dim):
        base = (
            _WEIGHT_TITLE * e_title[i]
            + _WEIGHT_GENRES * e_genres[i]
            + _WEIGHT_TAGS * e_tags[i]
        )
        extra = numeric_bias[i] if i < len(numeric_bias) else 0.0
        combined.append(base + extra)

    return l2_normalize(combined)


def bounds_from_items(items: list[Item]) -> tuple[tuple[int, int], tuple[int, int]]:
    years = [it.year for it in items]
    durs = [it.duration for it in items]
    return (min(years), max(years)), (min(durs), max(durs))
