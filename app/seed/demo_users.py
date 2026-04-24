"""Pre-carga de eventos demo en el Redis Stream (una vez por instancia de datos).

Borra la clave ``recommend:demo_seed_done`` en Redis si quieres volver a insertar el lote demo
(después vacía el stream si no quieres duplicados mezclados con datos reales).
"""

import logging
import time

from app.models.schemas import Event
from app.storage.redis_client import get_redis_client
from app.storage.user_state import append_event, get_user_state

logger = logging.getLogger(__name__)

SEED_DONE_KEY = "recommend:demo_seed_done"


def _demo_events() -> list[Event]:
    now = time.time()
    return [
        Event("demo-accion", "item-1", "like", now - 7200),
        Event("demo-accion", "item-1", "watch", now - 3600),
        Event("demo-accion", "item-6", "click", now - 60),
        Event("demo-ml", "item-4", "like", now - 1800),
        Event("demo-ml", "item-4", "watch", now - 120),
        Event("demo-ml", "item-1", "impression", now - 30),
        Event("demo-nature", "item-3", "watch", now - 2400),
        Event("demo-nature", "item-3", "like", now - 900),
        Event("demo-nature", "item-8", "impression", now - 120),
        Event("demo-dislike", "item-2", "like", now - 600),
        Event("demo-dislike", "item-2", "watch", now - 300),
        Event("demo-dislike", "item-1", "dislike", now - 60),
    ]


def seed_demo_stream_if_needed() -> None:
    """Añade eventos demo al stream si la marca no existe (idempotente por clave Redis)."""
    get_user_state()
    r = get_redis_client()
    if r.exists(SEED_DONE_KEY):
        logger.info("demo seed skipped (%s already set)", SEED_DONE_KEY)
        return

    events = sorted(
        _demo_events(),
        key=lambda e: (e.timestamp, e.user_id, e.item_id, e.event_type),
    )
    for event in events:
        append_event(event.user_id, event)

    r.set(SEED_DONE_KEY, "1")
    logger.info(
        "demo seed complete: %s events written for users demo-accion, demo-ml, demo-nature, demo-dislike",
        len(events),
    )
