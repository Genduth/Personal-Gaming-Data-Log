import os
from pathlib import Path

from sqlalchemy import text

from gamevault.db import get_engine


def run() -> None:
    directory = Path(
        os.environ.get(
            "GAMEVAULT_MIGRATIONS_DIR",
            str(Path.cwd() / "database" / "migrations"),
        )
    )
    if not directory.is_dir():
        raise RuntimeError(f"Migration directory not found: {directory}")
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS gaming"))
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gaming.schema_migrations (
                  version text PRIMARY KEY,
                  applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )

    for migration in sorted(directory.glob("*.sql")):
        with engine.begin() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM gaming.schema_migrations WHERE version = :version"),
                {"version": migration.name},
            ).scalar_one_or_none()
            if exists:
                continue
            raw = connection.connection.driver_connection
            if raw is None:
                raise RuntimeError("Database driver connection is unavailable")
            with raw.cursor() as cursor:
                cursor.execute(migration.read_text(encoding="utf-8"))
            connection.execute(
                text("INSERT INTO gaming.schema_migrations(version) VALUES (:version)"),
                {"version": migration.name},
            )
            print(f"Applied {migration.name}")


if __name__ == "__main__":
    run()
