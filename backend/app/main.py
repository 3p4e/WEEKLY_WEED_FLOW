"""WEEKLY_WEED_FLOW API entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, audit, auth, tasks
from app.config import settings
from app.db import close_pools, init_pools


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pools()
    yield
    await close_pools()


app = FastAPI(title="WEEKLY_WEED_FLOW API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(ai.router)
app.include_router(audit.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "system": "WEEKLY_WEED_FLOW API"}
