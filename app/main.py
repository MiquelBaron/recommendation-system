from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router as api_router
from app.seed.demo_users import seed_demo_stream_if_needed


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_demo_stream_if_needed()
    yield


app = FastAPI(title="Recommendation System API", lifespan=lifespan)
app.include_router(api_router)


@app.get("/", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
