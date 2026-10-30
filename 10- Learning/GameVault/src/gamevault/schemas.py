from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(StrEnum):
    start = "start"
    heartbeat = "heartbeat"
    stop = "stop"


class CollectorEvent(BaseModel):
    event_id: UUID
    event_type: EventType
    device_name: str = Field(min_length=1, max_length=100)
    executable: str = Field(min_length=1, max_length=260)
    occurred_at: datetime
    platform: str | None = Field(default=None, max_length=50)
    collector_version: str | None = Field(default=None, max_length=30)


class CollectorBatch(BaseModel):
    events: list[CollectorEvent] = Field(min_length=1, max_length=200)


class CollectorResult(BaseModel):
    event_id: UUID
    status: str
    session_id: UUID | None = None
    game_id: UUID | None = None


class AliasRequest(BaseModel):
    game_id: UUID
    executable: str = Field(min_length=1, max_length=260)
