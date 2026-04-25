"""Single entrypoint to load demo data (items + users + events).

Run manually:
    python -m app.seed.seed_examples

Use --force to ignore seed marker and push events again.
"""

import argparse
import logging
import time

from app.models.schemas import Event
from app.storage.catalog import CATALOG_ITEMS
from app.storage.postgres_store import ensure_postgres_schema, insert_event_durable, upsert_item_catalog
from app.storage.redis_client import get_redis_client
from app.storage.user_state import append_event, get_user_state

logger = logging.getLogger(__name__)

SEED_DONE_KEY = "recommend:demo_seed_done"


def _demo_events() -> list[Event]:
    now = time.time()
    return [
        # demo-accion: action/crime/racing bias with mixed signals.
        Event("demo-accion", "item-1", "impression", now - 21600),
        Event("demo-accion", "item-1", "watch", now - 21000),
        Event("demo-accion", "item-6", "click", now - 18000),
        Event("demo-accion", "item-12", "watch", now - 14400),
        Event("demo-accion", "item-12", "like", now - 10800),
        Event("demo-accion", "item-15", "click", now - 7200),
        Event("demo-accion", "item-15", "watch", now - 5400),
        Event("demo-accion", "item-2", "impression", now - 2400),
        Event("demo-accion", "item-14", "dislike", now - 1800),
        Event("demo-accion", "item-6", "like", now - 300),
        # demo-ml: education/technology bias, occasional sci-fi.
        Event("demo-ml", "item-4", "impression", now - 25200),
        Event("demo-ml", "item-4", "watch", now - 21600),
        Event("demo-ml", "item-10", "click", now - 18000),
        Event("demo-ml", "item-10", "watch", now - 14400),
        Event("demo-ml", "item-10", "like", now - 10800),
        Event("demo-ml", "item-9", "watch", now - 7200),
        Event("demo-ml", "item-9", "click", now - 4800),
        Event("demo-ml", "item-1", "impression", now - 1800),
        Event("demo-ml", "item-5", "dislike", now - 900),
        Event("demo-ml", "item-4", "like", now - 180),
        # demo-nature: strong documentary/nature preference.
        Event("demo-nature", "item-3", "impression", now - 28800),
        Event("demo-nature", "item-3", "watch", now - 24000),
        Event("demo-nature", "item-11", "click", now - 19200),
        Event("demo-nature", "item-11", "watch", now - 15000),
        Event("demo-nature", "item-16", "watch", now - 10800),
        Event("demo-nature", "item-16", "like", now - 7200),
        Event("demo-nature", "item-8", "impression", now - 3600),
        Event("demo-nature", "item-9", "impression", now - 2400),
        Event("demo-nature", "item-2", "dislike", now - 1200),
        Event("demo-nature", "item-3", "like", now - 240),
    ]


def seed_example_data(*, force: bool = False) -> None:
    """Seed all demo resources in one place: catalog rows + demo events."""
    ensure_postgres_schema()
    for item in CATALOG_ITEMS:
        upsert_item_catalog(
            item.id,
            item.title,
            {
                "genres": item.genres,
                "tags": item.tags,
                "year": item.year,
                "duration": item.duration,
            },
        )

    get_user_state()
    r = get_redis_client()
    if r.exists(SEED_DONE_KEY) and not force:
        logger.info("seed skipped (%s already set)", SEED_DONE_KEY)
        return

    events = sorted(
        _demo_events(),
        key=lambda e: (e.timestamp, e.user_id, e.item_id, e.event_type),
    )
    for event in events:
        insert_event_durable(event, source="seed")
        append_event(event.user_id, event)

    r.set(SEED_DONE_KEY, "1")
    users = sorted({e.user_id for e in events})
    logger.info(
        "seed complete: items=%s users=%s events=%s",
        len(CATALOG_ITEMS),
        len(users),
        len(events),
    )


def _configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo items/users/events")
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore seed marker and push demo events again",
    )
    args = parser.parse_args()
    _configure_logging()
    seed_example_data(force=args.force)


if __name__ == "__main__":
    main()
