from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router as api_router
from app.seed.seed_examples import seed_example_data


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Keep startup behavior, but call the centralized seed command entrypoint.
    seed_example_data()
    yield


app = FastAPI(title="Recommendation System API", lifespan=lifespan)
app.include_router(api_router)


@app.get("/", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
