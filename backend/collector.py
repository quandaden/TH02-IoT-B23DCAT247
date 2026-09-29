from __future__ import annotations

import argparse
import json
import logging
import signal
import ssl
import sys
import time
from dataclasses import dataclass

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from iot_pipeline.config import Settings
from iot_pipeline.influx_store import InfluxStore
from iot_pipeline.models import IngestRecord, SensorPayload
from iot_pipeline.sequence_tracker import SequenceObservation, SequenceTracker


LOG = logging.getLogger("collector")


@dataclass(frozen=True)
class ProcessedMessage:
    record: IngestRecord
    observation: SequenceObservation


class MessageProcessor:
    def __init__(self) -> None:
        self.tracker = SequenceTracker()

    def process(self, raw_payload: bytes | str, received_at_ms: int) -> ProcessedMessage:
        payload = SensorPayload.model_validate_json(raw_payload)
        observation = self.tracker.observe(
            payload.device_id, payload.sequence, payload.uptime_s
        )
        latency_ms = received_at_ms - payload.sent_at_ms
        record = IngestRecord(
            payload=payload,
            received_at_ms=received_at_ms,
            latency_ms=latency_ms,
            sequence_status=observation.status,
            gap_count=observation.gap_count,
        )
        return ProcessedMessage(record, observation)


class Collector:
    def __init__(self, settings: Settings, store: InfluxStore) -> None:
        self.settings = settings
        self.store = store
        self.processor = MessageProcessor()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"collector-b23dcat247-{int(time.time())}",
            protocol=mqtt.MQTTv311,
        )
        if settings.mqtt_username:
            self.client.username_pw_set(
                settings.mqtt_username, settings.mqtt_password
            )
        if settings.mqtt_tls_enabled:
            self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            self.client.tls_insecure_set(settings.mqtt_tls_insecure)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            LOG.error("MQTT connection rejected: %s", reason_code)
            return
        LOG.info("MQTT connected: %s:%s", self.settings.mqtt_host, self.settings.mqtt_port)
        client.subscribe(self.settings.mqtt_topic, qos=0)
        LOG.info("MQTT subscribed: %s", self.settings.mqtt_topic)

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ) -> None:
        if reason_code != 0:
            LOG.warning("MQTT disconnected unexpectedly: %s", reason_code)
        else:
            LOG.info("MQTT disconnected")

    def _on_message(self, client, userdata, message) -> None:
        received_at_ms = int(time.time() * 1000)
        try:
            result = self.processor.process(message.payload, received_at_ms)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            LOG.warning("VALIDATION REJECTED topic=%s error=%s", message.topic, exc)
            return

        data = result.record.payload
        if not result.observation.should_store:
            LOG.warning(
                "SEQUENCE SKIPPED device=%s sequence=%s status=%s",
                data.device_id,
                data.sequence,
                result.observation.status,
            )
            return

        try:
            self.store.write_raw(result.record)
        except Exception:
            LOG.exception(
                "INFLUX WRITE FAILED device=%s sequence=%s", data.device_id, data.sequence
            )
            return

        LOG.info(
            "INGEST OK device=%s sequence=%s status=%s gap=%s latency_ms=%s "
            "temperature=%.2f humidity=%.2f distance_cm=%.2f",
            data.device_id,
            data.sequence,
            result.observation.status,
            result.observation.gap_count,
            result.record.latency_ms,
            data.temperature,
            data.humidity,
            data.distance_cm,
        )

    def run(self) -> None:
        LOG.info("Connecting to MQTT broker...")
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=60)
        self.client.loop_forever(retry_first_connection=True)

    def stop(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()


def check_payload(payload: str) -> int:
    processor = MessageProcessor()
    try:
        result = processor.process(payload, int(time.time() * 1000))
    except ValidationError as exc:
        print(f"INVALID: {exc}")
        return 1
    print("VALID")
    print(result.record.payload.model_dump_json(indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MQTT to InfluxDB collector")
    parser.add_argument(
        "--check-payload",
        help="Validate one JSON payload without connecting to MQTT or InfluxDB",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    if args.check_payload:
        return check_payload(args.check_payload)

    settings = Settings.from_env()
    store = InfluxStore(settings)
    store.wait_until_ready()
    store.ensure_buckets()
    collector = Collector(settings, store)

    def stop_handler(signum, frame) -> None:
        LOG.info("Stopping collector")
        collector.stop()
        store.close()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    try:
        collector.run()
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

