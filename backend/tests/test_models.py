from __future__ import annotations

import json
import unittest

from pydantic import ValidationError

from iot_pipeline.models import SensorPayload


def valid_payload() -> dict:
    return {
        "device_id": "esp32-b23dcat247",
        "sent_at_ms": 1_790_672_400_000,
        "temperature": 25.0,
        "humidity": 50.0,
        "distance_cm": 100.0,
        "rssi": -70,
        "sequence": 1,
        "uptime_s": 5,
    }


class SensorPayloadTests(unittest.TestCase):
    def test_accepts_valid_payload(self) -> None:
        model = SensorPayload.model_validate_json(json.dumps(valid_payload()))
        self.assertEqual(model.device_id, "esp32-b23dcat247")
        self.assertEqual(model.sequence, 1)

    def test_rejects_out_of_range_humidity(self) -> None:
        payload = valid_payload()
        payload["humidity"] = 120
        with self.assertRaises(ValidationError):
            SensorPayload.model_validate(payload)

    def test_rejects_unknown_field(self) -> None:
        payload = valid_payload()
        payload["unexpected"] = "not allowed"
        with self.assertRaises(ValidationError):
            SensorPayload.model_validate(payload)


if __name__ == "__main__":
    unittest.main()

