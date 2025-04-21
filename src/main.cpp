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

// 猫娘注释：计算校验和的函数喵～
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

// 猫娘注释：检查并重连 WiFi 的函数喵～
void checkWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection lost, trying to reconnect..."); // 猫娘提示：丢失连接，正在重连喵～
    WiFi.disconnect();
    WiFi.begin(ssid, password);
    // 等待连接恢复
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    Serial.println("");
    Serial.println("WiFi reconnected successfully!"); // 猫娘激动：重连成功喵～
    IPAddress ip = WiFi.localIP();
    Serial.print("New IP address: ");
    Serial.println(ip);
    server.begin(); // 确保 WebServer 继续工作喵～
  }
}

void setup() {
  Serial.begin(19200);
  Wire.begin(4, 5);
  while (!bme.begin(0x76, &Wire)) {
    Serial.println("Could not find a valid BME280 sensor."); // 猫娘小声嘟囔：找不到传感器喵～
    delay(500);
  }

  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::FILTER_OFF);

  // 开始连接 WiFi
  WiFi.setAutoReconnect(true); // 猫娘设置：启用自动重连喵～
  WiFi.persistent(true);       // 猫娘设置：持久化配置喵～
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting to WiFi..."); // 猫娘：正在连接 WiFi 喵～
  }
  Serial.println("Connected to WiFi"); // 猫娘欢呼：连接成功喵～

  // 设置 HTTP GET 处理
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
    ESP.reset(); // 如果进入 AP fallback，就重启喵～
  }
  server.begin();
}

void loop() {
  server.handleClient();

  // 每次循环都检查一下 WiFi 状态并重连喵～
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
