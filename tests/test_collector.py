from datetime import UTC, datetime, timedelta

from collector.gamevault_collector import calculate_transitions


def test_emits_start_and_stop_events() -> None:
    now = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
    active, events = calculate_transitions(
        {"old-game.exe": (now - timedelta(seconds=30)).isoformat()},
        {"new-game.exe"},
        now,
        60,
    )

    assert set(active) == {"new-game.exe"}
    assert [(event["event_type"], event["executable"]) for event in events] == [
        ("start", "new-game.exe"),
        ("stop", "old-game.exe"),
    ]


def test_heartbeat_is_rate_limited() -> None:
    now = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
    active, events = calculate_transitions(
        {"game.exe": (now - timedelta(seconds=61)).isoformat()},
        {"game.exe"},
        now,
        60,
    )

    assert events[0]["event_type"] == "heartbeat"
    assert active["game.exe"].endswith("Z")


def test_no_early_heartbeat() -> None:
    now = datetime(2026, 10, 30, 20, 0, tzinfo=UTC)
    _, events = calculate_transitions(
        {"game.exe": (now - timedelta(seconds=20)).isoformat()},
        {"game.exe"},
        now,
        60,
    )
    assert events == []
