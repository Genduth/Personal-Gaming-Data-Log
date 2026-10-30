import argparse

from sqlalchemy import text

from gamevault.db import get_engine
from gamevault.migrate import run as migrate
from gamevault.services.steam import sync_steam
from gamevault.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="gamevault")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("migrate", help="Apply pending database migrations")
    subcommands.add_parser("steam-sync", help="Import Steam library and achievements")
    alias = subcommands.add_parser("add-alias", help="Map a process executable to a game")
    alias.add_argument("game_id")
    alias.add_argument("executable")
    arguments = parser.parse_args()

    if arguments.command == "migrate":
        migrate()
        return

    with get_engine().connect() as connection:
        if arguments.command == "steam-sync":
            print(sync_steam(connection, get_settings()))
            return
        with connection.begin():
            connection.execute(
                text(
                    """
                    INSERT INTO gaming.game_aliases (game_id, executable)
                    VALUES (:game_id, lower(:executable))
                    ON CONFLICT (lower(executable)) DO UPDATE SET game_id = EXCLUDED.game_id
                    """
                ),
                {"game_id": arguments.game_id, "executable": arguments.executable},
            )
        print(f"Mapped {arguments.executable.lower()} to {arguments.game_id}")


if __name__ == "__main__":
    main()
