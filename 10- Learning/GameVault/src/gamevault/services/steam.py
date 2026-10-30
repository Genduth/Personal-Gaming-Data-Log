import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import Connection, text

from gamevault.settings import Settings


def _slugify(value: str) -> str:
    slug = "".join(character.lower() if character.isalnum() else "-" for character in value)
    return "-".join(part for part in slug.split("-") if part)


class SteamClient:
    def __init__(self, api_key: str, steam_id: str) -> None:
        self.api_key = api_key
        self.steam_id = steam_id
        self.client = httpx.Client(base_url="https://api.steampowered.com", timeout=30)

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            response = self.client.get(path, params=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("Steam API request failed") from error

    def profile(self) -> dict[str, Any] | None:
        payload = self._get(
            "/ISteamUser/GetPlayerSummaries/v0002/",
            {"key": self.api_key, "steamids": self.steam_id},
        )
        players = payload.get("response", {}).get("players", [])
        return players[0] if players else None

    def owned_games(self) -> list[dict[str, Any]]:
        payload = self._get(
            "/IPlayerService/GetOwnedGames/v0001/",
            {
                "key": self.api_key,
                "steamid": self.steam_id,
                "include_appinfo": "1",
                "include_played_free_games": "1",
                "format": "json",
            },
        )
        return payload.get("response", {}).get("games", [])  # type: ignore[no-any-return]

    def achievements(self, app_id: int) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, float]]:
        player = self._get(
            "/ISteamUserStats/GetPlayerAchievements/v0001/",
            {
                "key": self.api_key,
                "steamid": self.steam_id,
                "appid": str(app_id),
                "l": "english",
            },
        )
        if not player.get("playerstats", {}).get("success"):
            return [], {}, {}
        schema_payload = self._get(
            "/ISteamUserStats/GetSchemaForGame/v2/",
            {"key": self.api_key, "appid": str(app_id), "l": "english"},
        )
        global_payload = self._get(
            "/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v0002/",
            {"gameid": str(app_id), "format": "json"},
        )
        schema = {
            item["name"]: item
            for item in schema_payload.get("game", {}).get("availableGameStats", {}).get("achievements", [])
        }
        rarity = {
            item["name"]: float(item["percent"])
            for item in global_payload.get("achievementpercentages", {}).get("achievements", [])
        }
        return player["playerstats"].get("achievements", []), schema, rarity

    def close(self) -> None:
        self.client.close()


def _upsert_account(connection: Connection, profile: dict[str, Any] | None, steam_id: str) -> UUID:
    return connection.execute(
        text(
            """
            INSERT INTO gaming.accounts
              (provider, external_id, display_name, profile_url, avatar_url, last_synced_at, metadata)
            VALUES (
              'steam', :external_id, :display_name, :profile_url, :avatar_url, now(),
              CAST(:metadata AS jsonb)
            )
            ON CONFLICT (provider, external_id) DO UPDATE SET
              display_name = EXCLUDED.display_name,
              profile_url = EXCLUDED.profile_url,
              avatar_url = EXCLUDED.avatar_url,
              last_synced_at = now(),
              metadata = EXCLUDED.metadata,
              updated_at = now()
            RETURNING account_id
            """
        ),
        {
            "external_id": steam_id,
            "display_name": profile.get("personaname") if profile else None,
            "profile_url": profile.get("profileurl") if profile else None,
            "avatar_url": profile.get("avatarfull") if profile else None,
            "metadata": json.dumps(
                {
                    "visibility_state": profile.get("communityvisibilitystate") if profile else None,
                    "country_code": profile.get("loccountrycode") if profile else None,
                }
            ),
        },
    ).scalar_one()


def sync_steam(connection: Connection, settings: Settings) -> dict[str, int | str]:
    if not settings.steam_api_key or not settings.steam_id:
        raise RuntimeError("STEAM_API_KEY and STEAM_ID must be configured")

    started_at = datetime.now(UTC)
    run_id: UUID = connection.execute(
        text(
            """
            INSERT INTO gaming.sync_runs (provider, status, started_at)
            VALUES ('steam', 'running', :started_at)
            RETURNING sync_run_id
            """
        ),
        {"started_at": started_at},
    ).scalar_one()
    connection.commit()
    client = SteamClient(settings.steam_api_key, settings.steam_id)

    try:
        profile = client.profile()
        games = client.owned_games()
        captured_at = datetime.now(UTC)
        with connection.begin():
            account_id = _upsert_account(connection, profile, settings.steam_id)
            stored: list[tuple[UUID, dict[str, Any]]] = []
            for game in games:
                app_id = int(game["appid"])
                title = str(game.get("name") or f"Steam app {app_id}")
                game_id: UUID = connection.execute(
                    text(
                        """
                        INSERT INTO gaming.games
                          (title, slug, primary_platform, provider, external_id, cover_url,
                           lifetime_playtime_minutes, last_played_at, metadata)
                        VALUES
                          (:title, :slug, 'PC', 'steam', :external_id, :cover_url,
                           :playtime, :last_played_at, CAST(:metadata AS jsonb))
                        ON CONFLICT (provider, external_id) DO UPDATE SET
                          title = EXCLUDED.title,
                          slug = EXCLUDED.slug,
                          cover_url = EXCLUDED.cover_url,
                          lifetime_playtime_minutes = EXCLUDED.lifetime_playtime_minutes,
                          last_played_at = greatest(gaming.games.last_played_at, EXCLUDED.last_played_at),
                          metadata = EXCLUDED.metadata,
                          updated_at = now()
                        RETURNING game_id
                        """
                    ),
                    {
                        "title": title,
                        "slug": _slugify(title) or f"steam-{app_id}",
                        "external_id": str(app_id),
                        "cover_url": (
                            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg"
                        ),
                        "playtime": int(game.get("playtime_forever", 0)),
                        "last_played_at": (
                            datetime.fromtimestamp(int(game["rtime_last_played"]), UTC)
                            if game.get("rtime_last_played")
                            else None
                        ),
                        "metadata": json.dumps(
                            {
                                "app_id": app_id,
                                "icon_hash": game.get("img_icon_url"),
                            }
                        ),
                    },
                ).scalar_one()
                connection.execute(
                    text(
                        """
                        INSERT INTO gaming.playtime_snapshots
                          (game_id, account_id, captured_at, lifetime_playtime_minutes,
                           recent_playtime_minutes, provider)
                        VALUES (:game_id, :account_id, :captured_at, :lifetime, :recent, 'steam')
                        ON CONFLICT (game_id, captured_at) DO NOTHING
                        """
                    ),
                    {
                        "game_id": game_id,
                        "account_id": account_id,
                        "captured_at": captured_at,
                        "lifetime": int(game.get("playtime_forever", 0)),
                        "recent": game.get("playtime_2weeks"),
                    },
                )
                stored.append((game_id, game))

        candidates = sorted(
            (item for item in stored if int(item[1].get("playtime_forever", 0)) > 0),
            key=lambda item: int(item[1].get("playtime_forever", 0)),
            reverse=True,
        )
        if settings.steam_achievement_game_limit:
            candidates = candidates[: settings.steam_achievement_game_limit]

        achievement_count = 0
        warning_count = 0
        for game_id, game in candidates:
            try:
                achievements, schema, rarity = client.achievements(int(game["appid"]))
                with connection.begin():
                    for achievement in achievements:
                        external_id = achievement["apiname"]
                        details = schema.get(external_id, {})
                        connection.execute(
                            text(
                                """
                                INSERT INTO gaming.achievements
                                  (game_id, provider, external_id, name, description, icon_url,
                                   is_unlocked, unlocked_at, is_hidden, rarity_percent, metadata)
                                VALUES
                                  (:game_id, 'steam', :external_id, :name, :description, :icon_url,
                                   :is_unlocked, :unlocked_at, :is_hidden, :rarity_percent,
                                   CAST(:metadata AS jsonb))
                                ON CONFLICT (game_id, provider, external_id) DO UPDATE SET
                                  name = EXCLUDED.name,
                                  description = EXCLUDED.description,
                                  icon_url = EXCLUDED.icon_url,
                                  is_unlocked = EXCLUDED.is_unlocked,
                                  unlocked_at = EXCLUDED.unlocked_at,
                                  is_hidden = EXCLUDED.is_hidden,
                                  rarity_percent = EXCLUDED.rarity_percent,
                                  metadata = EXCLUDED.metadata,
                                  updated_at = now()
                                """
                            ),
                            {
                                "game_id": game_id,
                                "external_id": external_id,
                                "name": details.get("displayName", external_id),
                                "description": details.get("description"),
                                "icon_url": details.get("icon"),
                                "is_unlocked": bool(achievement.get("achieved")),
                                "unlocked_at": (
                                    datetime.fromtimestamp(int(achievement["unlocktime"]), UTC)
                                    if achievement.get("unlocktime")
                                    else None
                                ),
                                "is_hidden": bool(details.get("hidden", 0)),
                                "rarity_percent": rarity.get(external_id),
                                "metadata": json.dumps({"app_id": int(game["appid"])}),
                            },
                        )
                        achievement_count += 1
            except RuntimeError:
                warning_count += 1

        status = "partial" if warning_count else "success"
        records = len(games) + achievement_count
        with connection.begin():
            connection.execute(
                text(
                    """
                    UPDATE gaming.sync_runs SET
                      status = :status,
                      finished_at = now(),
                      records_processed = :records,
                      warning_count = :warnings,
                      metadata = CAST(:metadata AS jsonb)
                    WHERE sync_run_id = :run_id
                    """
                ),
                {
                    "status": status,
                    "records": records,
                    "warnings": warning_count,
                    "metadata": json.dumps(
                        {
                            "games": len(games),
                            "achievements": achievement_count,
                            "achievement_games_attempted": len(candidates),
                        }
                    ),
                    "run_id": run_id,
                },
            )
        return {
            "run_id": str(run_id),
            "games": len(games),
            "achievements": achievement_count,
            "warnings": warning_count,
        }
    except Exception as error:
        connection.rollback()
        with connection.begin():
            connection.execute(
                text(
                    """
                    UPDATE gaming.sync_runs SET status = 'failed', finished_at = now(),
                      error_message = :error WHERE sync_run_id = :run_id
                    """
                ),
                {"error": str(error)[:1000], "run_id": run_id},
            )
        raise
    finally:
        client.close()
