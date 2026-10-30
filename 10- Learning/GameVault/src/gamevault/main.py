from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from gamevault import __version__
from gamevault.db import get_engine
from gamevault.routers.collector import router as collector_router
from gamevault.routers.sync import router as sync_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="GameVault API",
    version=__version__,
    description="Ingestion and synchronization API for the GameVault Power BI project.",
    lifespan=lifespan,
)
app.include_router(collector_router)
app.include_router(sync_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "version": __version__}
