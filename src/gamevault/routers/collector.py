from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection

from gamevault.auth import require_collector_token
from gamevault.db import database_connection
from gamevault.schemas import AliasRequest, CollectorBatch
from gamevault.services.collector import ingest_event

router = APIRouter(
    prefix="/v1/collector",
    tags=["collector"],
    dependencies=[Depends(require_collector_token)],
)
Database = Annotated[Connection, Depends(database_connection)]


@router.get("/catalog")
def catalog(connection: Database) -> dict[str, object]:
    rows = connection.execute(
        text(
            """
            SELECT a.executable, g.game_id, g.title
            FROM gaming.game_aliases a
            JOIN gaming.games g ON g.game_id = a.game_id
            ORDER BY g.title, a.executable
            """
        )
    ).mappings()
    return {"aliases": [dict(row) for row in rows]}


@router.post("/events")
def events(batch: CollectorBatch, connection: Database) -> dict[str, object]:
    with connection.begin():
        results = [ingest_event(connection, event) for event in batch.events]
    return {"accepted": len(results), "results": results}


@router.post("/aliases")
def add_alias(alias: AliasRequest, connection: Database) -> dict[str, str]:
    executable = alias.executable.strip().lower()
    with connection.begin():
        connection.execute(
            text(
                """
                INSERT INTO gaming.game_aliases (game_id, executable)
                VALUES (:game_id, :executable)
                ON CONFLICT (lower(executable)) DO UPDATE
                SET game_id = EXCLUDED.game_id
                """
            ),
            {"game_id": alias.game_id, "executable": executable},
        )
    return {"status": "mapped", "executable": executable}
