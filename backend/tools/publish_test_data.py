from __future__ import annotations

import argparse
import json
import ssl
import time

import paho.mqtt.client as mqtt

from iot_pipeline.config import Settings


SAMPLES = (
    (20.0, 35.0, 20.0),
    (25.0, 50.0, 50.0),
    (30.0, 65.0, 100.0),
    (35.0, 80.0, 200.0),
    (70.0, 55.0, 400.0),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish deterministic TH02 test data")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument(
        "--include-errors",
        action="store_true",
        help="Also publish malformed, duplicate and sequence-gap cases",
    )
    args = parser.parse_args()
    settings = Settings.from_env()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"th02-test-publisher-{int(time.time())}",
    )
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    if settings.mqtt_tls_enabled:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        client.tls_insecure_set(settings.mqtt_tls_insecure)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    client.loop_start()

    started = time.monotonic()
    sequence = 1
    try:
        for temperature, humidity, distance in SAMPLES:
            payload = {
                "device_id": "test-b23dcat247",
                "sent_at_ms": int(time.time() * 1000),
                "temperature": temperature,
                "humidity": humidity,
                "distance_cm": distance,
                "rssi": -70,
                "sequence": sequence,
                "uptime_s": int(time.monotonic() - started),
            }
            client.publish(settings.mqtt_topic, json.dumps(payload), qos=0).wait_for_publish()
            print(f"PUBLISHED sequence={sequence}: {payload}")
            sequence += 1
            time.sleep(args.interval)

        if args.include_errors:
            client.publish(settings.mqtt_topic, "{invalid-json", qos=0).wait_for_publish()
            print("PUBLISHED malformed JSON")

            duplicate = payload.copy()
            duplicate["sent_at_ms"] = int(time.time() * 1000)
            client.publish(
                settings.mqtt_topic, json.dumps(duplicate), qos=0
            ).wait_for_publish()
            print(f"PUBLISHED duplicate sequence={duplicate['sequence']}")

            gap = payload.copy()
            gap["sent_at_ms"] = int(time.time() * 1000)
            gap["sequence"] = sequence + 2
            gap["uptime_s"] += 5
            client.publish(settings.mqtt_topic, json.dumps(gap), qos=0).wait_for_publish()
            print(f"PUBLISHED sequence gap={gap['sequence']}")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

