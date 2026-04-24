from app.ml.item_embedding import bounds_from_items, item_to_embedding
from app.models.item import Item

CATALOG_ITEMS: list[Item] = [
    Item(
        id="item-1",
        title="Fast and Furious",
        genres=["action", "crime"],
        tags=["cars", "franchise", "heist"],
        year=2001,
        duration=106,
    ),
    Item(
        id="item-2",
        title="Titanic",
        genres=["romance", "drama"],
        tags=["ship", "historical", "disaster"],
        year=1997,
        duration=194,
    ),
    Item(
        id="item-3",
        title="Planeta Tierra",
        genres=["documentary", "nature"],
        tags=["wildlife", "bbc", "environment"],
        year=2006,
        duration=50,
    ),
    Item(
        id="item-4",
        title="Machine Learning con Python",
        genres=["education", "technology"],
        tags=["python", "course", "data science"],
        year=2020,
        duration=480,
    ),
    Item(
        id="item-5",
        title="El silencio de los corderos",
        genres=["thriller", "psychological"],
        tags=["suspense", "crime", "horror"],
        year=1991,
        duration=118,
    ),
    Item(
        id="item-6",
        title="The Avengers",
        genres=["action", "superhero"],
        tags=["marvel", "ensemble", "blockbuster"],
        year=2012,
        duration=143,
    ),
    Item(
        id="item-7",
        title="The Killing",
        genres=["mystery", "crime"],
        tags=["nordic noir", "detective", "series"],
        year=2007,
        duration=58,
    ),
    Item(
        id="item-8",
        title="Civilization VI",
        genres=["strategy", "simulation"],
        tags=["turn-based", "historical", "video game"],
        year=2016,
        duration=300,
    ),
]

_YEAR_BOUNDS, _DURATION_BOUNDS = bounds_from_items(CATALOG_ITEMS)

item_embeddings = {
    it.id: item_to_embedding(
        it,
        year_bounds=_YEAR_BOUNDS,
        duration_bounds=_DURATION_BOUNDS,
    )
    for it in CATALOG_ITEMS
}

# Nombre corto para respuestas API (título legible)
ITEMS: dict[str, str] = {it.id: it.title for it in CATALOG_ITEMS}
