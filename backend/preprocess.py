from __future__ import annotations

import argparse

from iot_pipeline.config import Settings
from iot_pipeline.influx_store import InfluxStore
from iot_pipeline.processing import preprocess_frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess raw IoT sensor data")
    parser.add_argument(
        "--start",
        default="-1h",
        help="Flux range start, for example -30m, -1h or -1d",
    )
    args = parser.parse_args()

    settings = Settings.from_env()
    store = InfluxStore(settings)
    try:
        raw = store.query_measurement(
            settings.influx_raw_bucket, "sensor_raw", start=args.start
        )
        if raw.empty:
            print("No raw records found; nothing to preprocess.")
            return

        processed = preprocess_frame(
            raw,
            frequency=settings.resample_frequency,
            rolling_window=settings.rolling_window,
        )
        count = store.write_processed(processed)
        outlier_count = int(processed.get("is_outlier", False).sum())
        print(
            f"Preprocessing complete: raw_rows={len(raw)}, "
            f"processed_rows={count}, outlier_rows={outlier_count}"
        )
        columns = [
            column
            for column in (
                "_time",
                "device_id",
                "temperature_raw",
                "temperature_clean",
                "temperature_rolling_mean",
                "temperature_normalized",
                "is_outlier",
            )
            if column in processed.columns
        ]
        print(processed[columns].tail(10).to_string(index=False))
    finally:
        store.close()


if __name__ == "__main__":
    main()

