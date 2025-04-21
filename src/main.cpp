#include <SPI.h>
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <Adafruit_BME280.h>
#include <ESP8266WebServer.h>

#define SYNC_WORD 0x8A

const char *ssid = "";
const char *password = "";

typedef struct {
  float data[4];
  uint8_t checksum;
} sensor_st;

sensor_st data;
Adafruit_BME280 bme;
ESP8266WebServer server(80);
unsigned long lastMeasure = 0;

uint8_t checksum(float *data, uint8_t length) {
  uint8_t checksum = 0;
  for (uint8_t i = 0; i < length; i++) {
    uint8_t *bytes = (uint8_t *)&data[i];
    for (uint8_t j = 0; j < sizeof(float); j++) {
      checksum ^= bytes[j];
    }
  }
  return checksum;
}

void checkWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection lost, trying to reconnect...");
    WiFi.disconnect();
    WiFi.begin(ssid, password);
    // 等待连接恢复
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    Serial.println("");
    Serial.println("WiFi reconnected successfully!");
    IPAddress ip = WiFi.localIP();
    Serial.print("New IP address: ");
    Serial.println(ip);
    server.begin();
  }
}

void setup() {
  Serial.begin(19200);
  Wire.begin(4, 5);
  while (!bme.begin(0x76, &Wire)) {
    Serial.println("Could not find a valid BME280 sensor.");
    delay(500);
  }

  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::FILTER_OFF);

  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  server.on("/", HTTP_GET, []() {
    char buffer[256];
    snprintf(buffer, sizeof(buffer),
             "{\"temperature\": %f, \"humidity\": %f, \"pressure\": %f}",
             data.data[0], data.data[1], data.data[2]);
    server.send(200, "application/json", buffer); });

  IPAddress ip = WiFi.localIP();
  Serial.print("ESP8266 Web Server's IP address: ");
  Serial.println(ip);
  if (ip[0] == 169 && ip[1] == 254) {
    ESP.reset();
  }
  server.begin();
}

void loop() {
  server.handleClient();

  checkWiFi();

  unsigned long now = millis();
  if (now - lastMeasure >= 60000) {
    lastMeasure = now;
    sensor_st dat;
    bme.takeForcedMeasurement();

    dat.data[0] = bme.readTemperature();
    dat.data[1] = bme.readHumidity();
    dat.data[2] = bme.readPressure() / 100.0F;
    dat.checksum = checksum(dat.data, 3);

    memcpy(&data, &dat, sizeof(sensor_st));
  }
}
