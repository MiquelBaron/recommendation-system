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
    Item(
        id="item-9",
        title="Interstellar",
        genres=["science fiction", "drama"],
        tags=["space", "time", "nolan"],
        year=2014,
        duration=169,
    ),
    Item(
        id="item-10",
        title="Deep Learning Fundamentals",
        genres=["education", "technology"],
        tags=["ai", "neural networks", "course"],
        year=2021,
        duration=620,
    ),
    Item(
        id="item-11",
        title="Blue Planet",
        genres=["documentary", "nature"],
        tags=["ocean", "wildlife", "bbc"],
        year=2001,
        duration=60,
    ),
    Item(
        id="item-12",
        title="John Wick",
        genres=["action", "thriller"],
        tags=["assassin", "revenge", "gun-fu"],
        year=2014,
        duration=101,
    ),
    Item(
        id="item-13",
        title="Mindhunter",
        genres=["crime", "psychological"],
        tags=["fbi", "serial killers", "series"],
        year=2017,
        duration=55,
    ),
    Item(
        id="item-14",
        title="The Notebook",
        genres=["romance", "drama"],
        tags=["love story", "classic", "tearjerker"],
        year=2004,
        duration=123,
    ),
    Item(
        id="item-15",
        title="Forza Horizon 5",
        genres=["racing", "simulation"],
        tags=["cars", "open world", "video game"],
        year=2021,
        duration=180,
    ),
    Item(
        id="item-16",
        title="Planet Earth II",
        genres=["documentary", "nature"],
        tags=["wildlife", "ecosystem", "cinematic"],
        year=2016,
        duration=50,
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
