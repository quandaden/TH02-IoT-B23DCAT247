from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _required(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _duration_seconds(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    text = value.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    suffix = text[-1]
    if suffix in multipliers:
        return int(text[:-1]) * multipliers[suffix]
    return int(text)


@dataclass(frozen=True)
class Settings:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_topic: str
    mqtt_tls_enabled: bool
    mqtt_tls_insecure: bool
    influx_url: str
    influx_org: str
    influx_token: str
    influx_raw_bucket: str
    influx_processed_bucket: str
    influx_raw_retention_seconds: int
    influx_processed_retention_seconds: int
    resample_frequency: str
    rolling_window: int
    dashboard_refresh_seconds: int

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or PROJECT_ROOT / ".env")
        return cls(
            mqtt_host=(
                os.getenv("MQTT_HOST")
                or os.getenv("MQTT_BROKER")
                or "127.0.0.1"
            ),
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_username=os.getenv("MQTT_USERNAME", ""),
            mqtt_password=os.getenv("MQTT_PASSWORD", ""),
            mqtt_topic=os.getenv("MQTT_TOPIC", "ptit/b23dcat247/sensors"),
            mqtt_tls_enabled=_as_bool(os.getenv("MQTT_TLS_ENABLED"), False),
            mqtt_tls_insecure=_as_bool(os.getenv("MQTT_TLS_INSECURE"), False),
            influx_url=os.getenv("INFLUX_URL", "http://localhost:8086"),
            influx_org=os.getenv("INFLUX_ORG", "ptit"),
            influx_token=_required("INFLUX_TOKEN"),
            influx_raw_bucket=os.getenv("INFLUX_RAW_BUCKET", "iot_raw"),
            influx_processed_bucket=os.getenv(
                "INFLUX_PROCESSED_BUCKET", "iot_processed"
            ),
            influx_raw_retention_seconds=_duration_seconds(
                os.getenv("INFLUX_RAW_RETENTION_SECONDS"), 604800
            ),
            influx_processed_retention_seconds=_duration_seconds(
                os.getenv("INFLUX_PROCESSED_RETENTION_SECONDS"), 2592000
            ),
            resample_frequency=os.getenv("RESAMPLE_FREQUENCY", "10s"),
            rolling_window=max(1, int(os.getenv("ROLLING_WINDOW", "3"))),
            dashboard_refresh_seconds=max(
                1, int(os.getenv("DASHBOARD_REFRESH_SECONDS", "5"))
            ),
        )

