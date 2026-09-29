#pragma once

// Copy this file to secrets.h, then replace the placeholder values.
// Never commit include/secrets.h.
namespace Secrets {
static constexpr char WIFI_SSID[] = "Wokwi-GUEST";
static constexpr char WIFI_PASSWORD[] = "";

static constexpr char MQTT_HOST[] = "host.wokwi.internal";
static constexpr unsigned int MQTT_PORT = 1883;
static constexpr char MQTT_USERNAME[] = "";
static constexpr char MQTT_PASSWORD[] = "";
static constexpr char MQTT_TOPIC[] = "ptit/b23dcat247/sensors";

// The local HiveMQ Docker broker currently exposes plain MQTT on port 1883.
// For production, expose port 8883, enable TLS and provide the broker CA.
static constexpr bool MQTT_TLS_ENABLED = false;
static constexpr bool ALLOW_INSECURE_TLS = false;
static constexpr char MQTT_ROOT_CA[] = "";
}

