from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules

from .config import Settings
from .models import IngestRecord


class InfluxStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = InfluxDBClient(
            url=settings.influx_url,
            token=settings.influx_token,
            org=settings.influx_org,
            timeout=10_000,
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def close(self) -> None:
        self.client.close()

    def wait_until_ready(self, timeout_seconds: int = 60) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if self.client.ping():
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError(f"InfluxDB did not become ready at {self.settings.influx_url}")

    def ensure_buckets(self) -> None:
        organizations = self.client.organizations_api().find_organizations(
            org=self.settings.influx_org
        )
        if not organizations:
            raise RuntimeError(f"InfluxDB organization not found: {self.settings.influx_org}")
        org_id = organizations[0].id
        buckets_api = self.client.buckets_api()
        existing = {bucket.name for bucket in buckets_api.find_buckets().buckets}

        definitions = (
            (
                self.settings.influx_raw_bucket,
                self.settings.influx_raw_retention_seconds,
            ),
            (
                self.settings.influx_processed_bucket,
                self.settings.influx_processed_retention_seconds,
            ),
        )
        for name, retention_seconds in definitions:
            if name in existing:
                continue
            buckets_api.create_bucket(
                bucket_name=name,
                org_id=org_id,
                retention_rules=[
                    BucketRetentionRules(
                        type="expire", every_seconds=retention_seconds
                    )
                ],
            )

    def write_raw(self, record: IngestRecord) -> None:
        data = record.payload
        point = (
            Point("sensor_raw")
            .tag("device_id", data.device_id)
            .tag("source", "wokwi")
            .field("temperature", float(data.temperature))
            .field("humidity", float(data.humidity))
            .field("distance_cm", float(data.distance_cm))
            .field("rssi", int(data.rssi))
            .field("sequence", int(data.sequence))
            .field("uptime_s", int(data.uptime_s))
            .field("sent_at_ms", int(data.sent_at_ms))
            .field("received_at_ms", int(record.received_at_ms))
            .field("latency_ms", int(record.latency_ms))
            .field("sequence_status", record.sequence_status)
            .field("gap_count", int(record.gap_count))
            .time(data.sent_at_ms, WritePrecision.MS)
        )
        self.write_api.write(
            bucket=self.settings.influx_raw_bucket,
            org=self.settings.influx_org,
            record=point,
        )

    def write_processed(self, frame: pd.DataFrame) -> int:
        points: list[Point] = []
        integer_fields = {
            "sequence",
            "uptime_s",
            "gap_count",
            "sent_at_ms",
            "received_at_ms",
        }
        for _, row in frame.iterrows():
            point = (
                Point("sensor_processed")
                .tag("device_id", str(row["device_id"]))
                .tag("source", "python-preprocessor")
                .time(pd.Timestamp(row["_time"]).to_pydatetime(), WritePrecision.MS)
            )
            for column, value in row.items():
                if column in {"_time", "device_id"} or pd.isna(value):
                    continue
                # Pandas can promote integer columns to float after resampling
                # (for example, sequence=12 becomes 12.0). InfluxDB fixes a
                # field's type on first write, so keep counter fields integer.
                if column in integer_fields:
                    point.field(column, int(value))
                elif isinstance(value, (np.bool_, bool)):
                    point.field(column, bool(value))
                elif isinstance(value, (np.integer, int)):
                    point.field(column, int(value))
                elif isinstance(value, (np.floating, float)):
                    point.field(column, float(value))
                elif isinstance(value, str):
                    point.field(column, value)
            points.append(point)

        if points:
            self.write_api.write(
                bucket=self.settings.influx_processed_bucket,
                org=self.settings.influx_org,
                record=points,
            )
        return len(points)

    def query_measurement(
        self, bucket: str, measurement: str, start: str = "-1h"
    ) -> pd.DataFrame:
        query = f'''
import "influxdata/influxdb/schema"

from(bucket: "{bucket}")
  |> range(start: {start})
  |> filter(fn: (r) => r["_measurement"] == "{measurement}")
  |> schema.fieldsAsCols()
  |> sort(columns: ["_time"])
'''
        result: Any = self.client.query_api().query_data_frame(
            query=query, org=self.settings.influx_org
        )
        if isinstance(result, list):
            frames = [item for item in result if not item.empty]
            if not frames:
                return pd.DataFrame()
            result = pd.concat(frames, ignore_index=True)
        if result is None or result.empty:
            return pd.DataFrame()
        return result.drop(
            columns=["result", "table", "_start", "_stop", "_measurement"],
            errors="ignore",
        )
