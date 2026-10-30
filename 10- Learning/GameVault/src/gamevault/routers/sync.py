from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Connection

from gamevault.auth import require_collector_token
from gamevault.db import database_connection
from gamevault.services.steam import sync_steam
from gamevault.settings import get_settings

router = APIRouter(
    prefix="/v1/sync",
    tags=["sync"],
    dependencies=[Depends(require_collector_token)],
)
Database = Annotated[Connection, Depends(database_connection)]


@router.post("/steam")
def steam(connection: Database) -> dict[str, int | str]:
    try:
        return sync_steam(connection, get_settings())
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
