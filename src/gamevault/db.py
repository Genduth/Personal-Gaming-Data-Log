from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from gamevault.settings import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)
    return _engine


def database_connection() -> Generator[Connection, None, None]:
    with get_engine().connect() as connection:
        yield connection
