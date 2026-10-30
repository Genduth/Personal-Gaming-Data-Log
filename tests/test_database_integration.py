import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from gamevault.db import get_engine
from gamevault.schemas import CollectorEvent, EventType
from gamevault.services import steam as steam_service
from gamevault.services.collector import ingest_event
from gamevault.settings import Settings

pytestmark = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL is required for PostgreSQL integration tests",
)


def test_collector_lifecycle_is_idempotent() -> None:
    suffix = uuid4().hex
    executable = f"game-{suffix}.exe"
    device = f"test-device-{suffix}"
    started_at = datetime(2026, 10, 30, 19, 0, tzinfo=UTC)

    with get_engine().connect() as connection, connection.begin():
        game_id = connection.execute(
            text(
                """
                INSERT INTO gaming.games
                  (title, slug, primary_platform, provider, external_id)
                VALUES ('Test Game', :slug, 'PC', 'test', :external_id)
                RETURNING game_id
                """
            ),
            {"slug": f"test-game-{suffix}", "external_id": suffix},
        ).scalar_one()
        connection.execute(
            text("INSERT INTO gaming.game_aliases(game_id, executable) VALUES (:id, :exe)"),
            {"id": game_id, "exe": executable},
        )

        start = CollectorEvent(
            event_id=uuid4(),
            event_type=EventType.start,
            device_name=device,
            executable=executable,
            occurred_at=started_at,
        )
        start_result = ingest_event(connection, start)
        duplicate_result = ingest_event(connection, start)
        stop_result = ingest_event(
            connection,
            CollectorEvent(
                event_id=uuid4(),
                event_type=EventType.stop,
                device_name=device,
                executable=executable,
                occurred_at=started_at + timedelta(minutes=90),
            ),
        )

        assert start_result.status == "started"
        assert duplicate_result.status == "duplicate"
        assert stop_result.status == "stopped"
        duration = connection.execute(
            text("SELECT duration_seconds FROM gaming.game_sessions WHERE session_id = :id"),
            {"id": start_result.session_id},
        ).scalar_one()
        assert duration == 90 * 60

        connection.execute(text("DELETE FROM gaming.games WHERE game_id = :id"), {"id": game_id})
        connection.execute(text("DELETE FROM gaming.devices WHERE device_name = :name"), {"name": device})


def test_steam_sync_writes_library_snapshots_and_achievements(monkeypatch: pytest.MonkeyPatch) -> None:
    suffix = uuid4().int % 1_000_000_000
    steam_id = f"7656119{suffix:010d}"

    class FakeSteamClient:
        def __init__(self, api_key: str, configured_steam_id: str) -> None:
            assert api_key == "test-key"
            assert configured_steam_id == steam_id

        def profile(self) -> dict[str, object]:
            return {"personaname": "Test Player", "communityvisibilitystate": 3}

        def owned_games(self) -> list[dict[str, object]]:
            return [
                {
                    "appid": suffix,
                    "name": "Integration Test Game",
                    "playtime_forever": 180,
                    "playtime_2weeks": 45,
                    "rtime_last_played": 1_798_000_000,
                }
            ]

        def achievements(
            self, app_id: int
        ) -> tuple[list[dict[str, object]], dict[str, object], dict[str, float]]:
            assert app_id == suffix
            return (
                [{"apiname": "TEST_UNLOCK", "achieved": 1, "unlocktime": 1_798_000_000}],
                {
                    "TEST_UNLOCK": {
                        "displayName": "Test Unlock",
                        "description": "Integration fixture",
                        "hidden": 0,
                    }
                },
                {"TEST_UNLOCK": 4.2},
            )

        def close(self) -> None:
            pass

    monkeypatch.setattr(steam_service, "SteamClient", FakeSteamClient)
    settings = Settings(
        database_url=os.environ["DATABASE_URL"],
        collector_token="test-collector-token-at-least-16-chars",
        steam_api_key="test-key",
        steam_id=steam_id,
        steam_achievement_game_limit=10,
    )
    with get_engine().connect() as connection:
        result = steam_service.sync_steam(connection, settings)
        game_id = connection.execute(
            text("SELECT game_id FROM gaming.games WHERE provider='steam' AND external_id=:id"),
            {"id": str(suffix)},
        ).scalar_one()
        snapshot_count = connection.execute(
            text("SELECT count(*) FROM gaming.playtime_snapshots WHERE game_id=:id"),
            {"id": game_id},
        ).scalar_one()
        achievement_count = connection.execute(
            text("SELECT count(*) FROM gaming.achievements WHERE game_id=:id AND is_unlocked"),
            {"id": game_id},
        ).scalar_one()

        assert result["games"] == 1
        assert result["achievements"] == 1
        assert snapshot_count == 1
        assert achievement_count == 1

        connection.commit()
        with connection.begin():
            connection.execute(text("DELETE FROM gaming.games WHERE game_id=:id"), {"id": game_id})
            connection.execute(
                text("DELETE FROM gaming.accounts WHERE provider='steam' AND external_id=:id"),
                {"id": steam_id},
            )
            connection.execute(
                text("DELETE FROM gaming.sync_runs WHERE sync_run_id=:id"),
                {"id": result["run_id"]},
            )
