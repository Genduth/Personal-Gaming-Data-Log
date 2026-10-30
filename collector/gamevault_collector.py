#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import platform
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VERSION = "0.1.0"


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def running_executables() -> set[str]:
    system = platform.system()
    if system == "Windows":
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/nh"],
            check=True,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {row[0].lower() for row in csv.reader(result.stdout.splitlines()) if row}
    if system == "Darwin":
        result = subprocess.run(["ps", "-axo", "comm="], check=True, capture_output=True, text=True)
        return {Path(line.strip()).name.lower() for line in result.stdout.splitlines() if line.strip()}

    processes: set[str] = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            processes.add((entry / "comm").read_text(encoding="utf-8").strip().lower())
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return processes


def create_event(event_type: str, executable: str, occurred_at: datetime) -> dict[str, str]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "executable": executable,
        "occurred_at": iso(occurred_at),
    }


def calculate_transitions(
    active: dict[str, str],
    running: set[str],
    now: datetime,
    heartbeat_seconds: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    events: list[dict[str, str]] = []
    next_active = dict(active)

    for executable in sorted(running - active.keys()):
        events.append(create_event("start", executable, now))
        next_active[executable] = iso(now)

    for executable in sorted(active.keys() - running):
        events.append(create_event("stop", executable, now))
        next_active.pop(executable, None)

    for executable in sorted(running & active.keys()):
        last_heartbeat = datetime.fromisoformat(active[executable].replace("Z", "+00:00"))
        if (now - last_heartbeat).total_seconds() >= heartbeat_seconds:
            events.append(create_event("heartbeat", executable, now))
            next_active[executable] = iso(now)

    return next_active, events


@dataclass(frozen=True)
class Config:
    api_url: str
    token: str
    device_name: str
    poll_seconds: int
    heartbeat_seconds: int
    state_path: Path

    @classmethod
    def from_environment(cls) -> Config:
        token = os.environ.get("GAMEVAULT_TOKEN") or os.environ.get("COLLECTOR_TOKEN")
        if not token:
            raise RuntimeError("Set GAMEVAULT_TOKEN before starting the collector")
        return cls(
            api_url=os.environ.get("GAMEVAULT_API_URL", "http://localhost:8000").rstrip("/"),
            token=token,
            device_name=os.environ.get("GAMEVAULT_DEVICE_NAME", socket.gethostname()),
            poll_seconds=max(5, int(os.environ.get("GAMEVAULT_POLL_SECONDS", "15"))),
            heartbeat_seconds=max(30, int(os.environ.get("GAMEVAULT_HEARTBEAT_SECONDS", "60"))),
            state_path=Path(
                os.environ.get(
                    "GAMEVAULT_STATE_PATH",
                    str(Path.home() / ".gamevault" / "collector-state.json"),
                )
            ),
        )


class Collector:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self.config.state_path.read_text(encoding="utf-8"))
            return {
                "active": dict(data.get("active", {})),
                "pending": list(data.get("pending", [])),
                "aliases": list(data.get("aliases", [])),
            }
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return {"active": {}, "pending": [], "aliases": []}

    def _save_state(self) -> None:
        self.config.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        temporary.replace(self.config.state_path)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.config.api_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.config.token}",
                "Content-Type": "application/json",
                "User-Agent": f"gamevault-collector/{VERSION}",
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)

    def refresh_catalog(self) -> None:
        payload = self._request("GET", "/v1/collector/catalog")
        self.state["aliases"] = sorted(
            {str(item["executable"]).lower() for item in payload.get("aliases", [])}
        )

    def send_pending(self) -> None:
        if not self.state["pending"]:
            return
        events = [
            {
                **event,
                "device_name": self.config.device_name,
                "platform": platform.system(),
                "collector_version": VERSION,
            }
            for event in self.state["pending"][:200]
        ]
        self._request("POST", "/v1/collector/events", {"events": events})
        del self.state["pending"][: len(events)]
        self._save_state()

    def poll(self) -> None:
        aliases = set(self.state["aliases"])
        running = running_executables() & aliases
        active, events = calculate_transitions(
            self.state["active"], running, utc_now(), self.config.heartbeat_seconds
        )
        self.state["active"] = active
        self.state["pending"].extend(events)
        self._save_state()
        self.send_pending()

    def run(self) -> None:
        print(f"GameVault collector {VERSION} tracking {self.config.device_name}")
        catalog_refresh_at = 0.0
        while True:
            try:
                if time.monotonic() >= catalog_refresh_at:
                    self.refresh_catalog()
                    catalog_refresh_at = time.monotonic() + 300
                self.poll()
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                print(f"Collector offline; events remain queued: {error}", file=sys.stderr)
            time.sleep(self.config.poll_seconds)


def main() -> None:
    Collector(Config.from_environment()).run()


if __name__ == "__main__":
    main()
