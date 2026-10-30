from uuid import UUID

from sqlalchemy import Connection, text

from gamevault.schemas import CollectorEvent, CollectorResult, EventType


def _device_id(connection: Connection, event: CollectorEvent) -> UUID:
    return connection.execute(
        text(
            """
            INSERT INTO gaming.devices
              (device_name, platform, collector_version, last_seen_at)
            VALUES (:device_name, :platform, :collector_version, :occurred_at)
            ON CONFLICT (device_name) DO UPDATE SET
              platform = coalesce(EXCLUDED.platform, gaming.devices.platform),
              collector_version = coalesce(EXCLUDED.collector_version, gaming.devices.collector_version),
              last_seen_at = greatest(gaming.devices.last_seen_at, EXCLUDED.last_seen_at)
            RETURNING device_id
            """
        ),
        event.model_dump(),
    ).scalar_one()


def ingest_event(connection: Connection, event: CollectorEvent) -> CollectorResult:
    device_id = _device_id(connection, event)
    executable = event.executable.strip().lower()
    inserted = connection.execute(
        text(
            """
            INSERT INTO gaming.collector_events
              (event_id, event_type, device_id, executable, occurred_at)
            VALUES (:event_id, :event_type, :device_id, :executable, :occurred_at)
            ON CONFLICT (event_id) DO NOTHING
            RETURNING event_id
            """
        ),
        {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "device_id": device_id,
            "executable": executable,
            "occurred_at": event.occurred_at,
        },
    ).scalar_one_or_none()
    if inserted is None:
        return CollectorResult(event_id=event.event_id, status="duplicate")

    game_id = connection.execute(
        text(
            """
            SELECT game_id FROM gaming.game_aliases
            WHERE lower(executable) = lower(:executable)
            """
        ),
        {"executable": executable},
    ).scalar_one_or_none()
    if game_id is None:
        connection.execute(
            text(
                """
                INSERT INTO gaming.unmatched_processes
                  (executable, device_id, first_seen_at, last_seen_at)
                VALUES (:executable, :device_id, :occurred_at, :occurred_at)
                ON CONFLICT (executable) DO UPDATE SET
                  device_id = EXCLUDED.device_id,
                  last_seen_at = greatest(
                    gaming.unmatched_processes.last_seen_at,
                    EXCLUDED.last_seen_at
                  ),
                  seen_count = gaming.unmatched_processes.seen_count + 1
                """
            ),
            {
                "executable": executable,
                "device_id": device_id,
                "occurred_at": event.occurred_at,
            },
        )
        return CollectorResult(event_id=event.event_id, status="unmatched")

    session_id = connection.execute(
        text(
            """
            SELECT session_id FROM gaming.game_sessions
            WHERE game_id = :game_id AND device_id = :device_id AND status = 'active'
            FOR UPDATE
            """
        ),
        {"game_id": game_id, "device_id": device_id},
    ).scalar_one_or_none()

    if event.event_type is EventType.start:
        if session_id is None:
            session_id = connection.execute(
                text(
                    """
                    INSERT INTO gaming.game_sessions
                      (game_id, device_id, source, executable, started_at,
                       last_heartbeat_at, status)
                    VALUES
                      (:game_id, :device_id, 'collector', :executable, :occurred_at,
                       :occurred_at, 'active')
                    RETURNING session_id
                    """
                ),
                {
                    "game_id": game_id,
                    "device_id": device_id,
                    "executable": executable,
                    "occurred_at": event.occurred_at,
                },
            ).scalar_one()
            result_status = "started"
        else:
            connection.execute(
                text(
                    """
                    UPDATE gaming.game_sessions
                    SET last_heartbeat_at = greatest(last_heartbeat_at, :occurred_at)
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id, "occurred_at": event.occurred_at},
            )
            result_status = "already_active"
    elif event.event_type is EventType.heartbeat:
        if session_id is None:
            return CollectorResult(event_id=event.event_id, status="no_active_session", game_id=game_id)
        connection.execute(
            text(
                """
                UPDATE gaming.game_sessions
                SET last_heartbeat_at = greatest(last_heartbeat_at, :occurred_at)
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id, "occurred_at": event.occurred_at},
        )
        result_status = "heartbeat"
    else:
        if session_id is None:
            return CollectorResult(event_id=event.event_id, status="no_active_session", game_id=game_id)
        connection.execute(
            text(
                """
                UPDATE gaming.game_sessions
                SET ended_at = greatest(started_at, :occurred_at),
                    last_heartbeat_at = greatest(last_heartbeat_at, :occurred_at),
                    status = 'closed'
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id, "occurred_at": event.occurred_at},
        )
        result_status = "stopped"

    connection.execute(
        text(
            """
            UPDATE gaming.collector_events SET session_id = :session_id
            WHERE event_id = :event_id
            """
        ),
        {"session_id": session_id, "event_id": event.event_id},
    )
    connection.execute(
        text(
            """
            UPDATE gaming.games
            SET last_played_at = greatest(last_played_at, :occurred_at), updated_at = now()
            WHERE game_id = :game_id
            """
        ),
        {"game_id": game_id, "occurred_at": event.occurred_at},
    )
    return CollectorResult(
        event_id=event.event_id,
        status=result_status,
        session_id=session_id,
        game_id=game_id,
    )
