import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_postgres_url() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    db = os.getenv("POSTGRES_DB", "recommender")
    user = os.getenv("POSTGRES_USER", "recommender")
    password = os.getenv("POSTGRES_PASSWORD", "recommender")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


_ENGINE = create_engine(
    get_postgres_url(),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=_ENGINE, autoflush=False, autocommit=False)


def get_postgres_engine():
    return _ENGINE
