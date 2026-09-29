#include <Arduino.h>
#include <DHTesp.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include <sys/time.h>
#include <time.h>

#include "secrets.h"

namespace {
constexpr char DEVICE_ID[] = "esp32-b23dcat247";
constexpr int DHT_PIN = 15;
constexpr int TRIG_PIN = 5;
constexpr int ECHO_PIN = 18;
constexpr int LED_PIN = 2;

constexpr unsigned long SEND_INTERVAL_MS = 5000;
constexpr unsigned long WIFI_RETRY_INTERVAL_MS = 5000;
constexpr unsigned long MQTT_RETRY_INTERVAL_MS = 5000;
constexpr unsigned long STATUS_INTERVAL_MS = 2000;

constexpr float MIN_TEMPERATURE_C = -40.0F;
constexpr float MAX_TEMPERATURE_C = 80.0F;
constexpr float MIN_HUMIDITY_PERCENT = 0.0F;
constexpr float MAX_HUMIDITY_PERCENT = 100.0F;
constexpr float MIN_DISTANCE_CM = 2.0F;
constexpr float MAX_DISTANCE_CM = 450.0F;

WiFiClient plainClient;
WiFiClientSecure tlsClient;
Client &networkClient = Secrets::MQTT_TLS_ENABLED
                            ? static_cast<Client &>(tlsClient)
                            : static_cast<Client &>(plainClient);
PubSubClient mqttClient(networkClient);
DHTesp dht;

unsigned long lastSendAt = 0;
unsigned long lastWiFiAttemptAt = 0;
unsigned long lastMqttAttemptAt = 0;
unsigned long lastStatusAt = 0;
unsigned long sequenceNo = 0;
bool ntpStarted = false;

void configureTransport() {
  if (!Secrets::MQTT_TLS_ENABLED) {
    Serial.println("MQTT transport: plain TCP for local Docker lab");
    return;
  }

  if (!Secrets::ALLOW_INSECURE_TLS && strlen(Secrets::MQTT_ROOT_CA) > 0) {
    tlsClient.setCACert(Secrets::MQTT_ROOT_CA);
    Serial.println("TLS: broker certificate verification enabled");
    return;
  }

  tlsClient.setInsecure();
  Serial.println("TLS: encrypted connection without certificate verification (lab only)");
}

void startWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(Secrets::WIFI_SSID, Secrets::WIFI_PASSWORD, 6);
  lastWiFiAttemptAt = millis();
  Serial.printf("WiFi: connecting to %s\n", Secrets::WIFI_SSID);
}

void maintainWiFi(unsigned long now) {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  if (now - lastWiFiAttemptAt >= WIFI_RETRY_INTERVAL_MS) {
    WiFi.disconnect();
    startWiFi();
  }
}

void startNtpIfNeeded() {
  if (ntpStarted || WiFi.status() != WL_CONNECTED) {
    return;
  }

  configTime(0, 0, "pool.ntp.org", "time.google.com", "time.cloudflare.com");
  ntpStarted = true;
  Serial.println("NTP: synchronization requested");
}

bool clockIsReady() {
  return time(nullptr) > 1700000000;
}

uint64_t epochMilliseconds() {
  timeval currentTime{};
  gettimeofday(&currentTime, nullptr);
  return static_cast<uint64_t>(currentTime.tv_sec) * 1000ULL +
         static_cast<uint64_t>(currentTime.tv_usec) / 1000ULL;
}

String mqttClientId() {
  const uint64_t chipId = ESP.getEfuseMac();
  char buffer[48];
  snprintf(buffer, sizeof(buffer), "%s-%08lx", DEVICE_ID,
           static_cast<unsigned long>(chipId & 0xFFFFFFFFULL));
  return String(buffer);
}

void maintainMqtt(unsigned long now) {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected()) {
    return;
  }

  if (now - lastMqttAttemptAt < MQTT_RETRY_INTERVAL_MS) {
    return;
  }

  lastMqttAttemptAt = now;
  const String clientId = mqttClientId();
  Serial.printf("MQTT: connecting to %s:%u as %s\n", Secrets::MQTT_HOST,
                Secrets::MQTT_PORT, clientId.c_str());

  const bool hasCredentials = strlen(Secrets::MQTT_USERNAME) > 0;
  const bool connected =
      hasCredentials
          ? mqttClient.connect(clientId.c_str(), Secrets::MQTT_USERNAME,
                               Secrets::MQTT_PASSWORD)
          : mqttClient.connect(clientId.c_str());

  if (connected) {
    Serial.printf("MQTT: connected, topic=%s\n", Secrets::MQTT_TOPIC);
  } else {
    Serial.printf("MQTT: connection failed, state=%d; retry in %lu ms\n",
                  mqttClient.state(), MQTT_RETRY_INTERVAL_MS);
  }
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) {
    return NAN;
  }
  return duration * 0.0343F / 2.0F;
}

bool sensorDataIsValid(const TempAndHumidity &data, float distance) {
  if (!isfinite(data.temperature) || !isfinite(data.humidity) ||
      !isfinite(distance)) {
    Serial.println("VALIDATION: rejected non-finite sensor value");
    return false;
  }

  const bool temperatureValid = data.temperature >= MIN_TEMPERATURE_C &&
                                data.temperature <= MAX_TEMPERATURE_C;
  const bool humidityValid = data.humidity >= MIN_HUMIDITY_PERCENT &&
                             data.humidity <= MAX_HUMIDITY_PERCENT;
  const bool distanceValid = distance >= MIN_DISTANCE_CM &&
                             distance <= MAX_DISTANCE_CM;

  if (!temperatureValid || !humidityValid || !distanceValid) {
    Serial.printf(
        "VALIDATION: rejected out-of-range data temp=%.2f humidity=%.2f "
        "distance=%.2f\n",
        data.temperature, data.humidity, distance);
    return false;
  }
  return true;
}

void publishSensorData(unsigned long now) {
  if (!mqttClient.connected() || !clockIsReady() ||
      now - lastSendAt < SEND_INTERVAL_MS) {
    return;
  }
  lastSendAt = now;

  const TempAndHumidity data = dht.getTempAndHumidity();
  const float distance = readDistanceCm();
  if (!sensorDataIsValid(data, distance)) {
    return;
  }

  sequenceNo++;
  const uint64_t sentAtMs = epochMilliseconds();
  char payload[384];
  snprintf(
      payload, sizeof(payload),
      "{\"device_id\":\"%s\",\"sent_at_ms\":%llu,\"temperature\":%.2f,"
      "\"humidity\":%.2f,\"distance_cm\":%.2f,\"rssi\":%d,"
      "\"sequence\":%lu,\"uptime_s\":%lu}",
      DEVICE_ID, static_cast<unsigned long long>(sentAtMs), data.temperature,
      data.humidity, distance, WiFi.RSSI(), sequenceNo, millis() / 1000UL);

  const bool published = mqttClient.publish(Secrets::MQTT_TOPIC, payload);
  Serial.printf("PUBLISH: topic=%s status=%s payload=%s\n", Secrets::MQTT_TOPIC,
                published ? "OK" : "FAILED", payload);

  if (published) {
    digitalWrite(LED_PIN, HIGH);
    delay(80);
    digitalWrite(LED_PIN, LOW);
  }
}

void printStatus(unsigned long now) {
  if (now - lastStatusAt < STATUS_INTERVAL_MS) {
    return;
  }
  lastStatusAt = now;

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("STATUS: waiting for WiFi");
  } else if (!clockIsReady()) {
    Serial.println("STATUS: WiFi connected, waiting for NTP");
  } else if (!mqttClient.connected()) {
    Serial.println("STATUS: time synchronized, waiting for MQTT");
  }
}
}  // namespace

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  dht.setup(DHT_PIN, DHTesp::DHT22);

  configureTransport();
  mqttClient.setServer(Secrets::MQTT_HOST, Secrets::MQTT_PORT);
  mqttClient.setBufferSize(512);
  mqttClient.setKeepAlive(30);
  mqttClient.setSocketTimeout(10);
  startWiFi();
}

void loop() {
  const unsigned long now = millis();
  maintainWiFi(now);
  startNtpIfNeeded();
  maintainMqtt(now);

  if (mqttClient.connected()) {
    mqttClient.loop();
  }

  publishSensorData(now);
  printStatus(now);
  delay(10);
}

