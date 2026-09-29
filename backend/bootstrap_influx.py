from __future__ import annotations

from iot_pipeline.config import Settings
from iot_pipeline.influx_store import InfluxStore


def main() -> None:
    settings = Settings.from_env()
    store = InfluxStore(settings)
    try:
        print(f"Waiting for InfluxDB at {settings.influx_url}...")
        store.wait_until_ready()
        store.ensure_buckets()
        print(
            "InfluxDB ready: "
            f"raw={settings.influx_raw_bucket}, "
            f"processed={settings.influx_processed_bucket}"
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()

