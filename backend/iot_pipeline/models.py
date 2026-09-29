from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class SensorPayload(BaseModel):
    """Validated JSON schema published by the ESP32."""

    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    sent_at_ms: int = Field(gt=1_700_000_000_000)
    temperature: float = Field(ge=-40.0, le=80.0)
    humidity: float = Field(ge=0.0, le=100.0)
    distance_cm: float = Field(ge=2.0, le=450.0)
    rssi: int = Field(ge=-127, le=0)
    sequence: int = Field(ge=1)
    uptime_s: int = Field(ge=0)


@dataclass(frozen=True)
class IngestRecord:
    payload: SensorPayload
    received_at_ms: int
    latency_ms: int
    sequence_status: str
    gap_count: int

