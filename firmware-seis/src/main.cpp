#include <SPI.h>
#include <Wire.h>
#include <Arduino.h>
#include <Adafruit_BME280.h>

#define SYNC_WORD 0x8A // 同步字节，用来标记数据开始

// 传感器数据结构：3个浮点数 + 1个校验和
typedef struct {
  float temperature;
  float humidity;
  float pressure;
  uint8_t checksum;
} sensor_st;

Adafruit_BME280 bme;           // BME280 传感器对象
unsigned long lastMeasure = 0; // 上次测量时间戳

// 计算浮点数组的异或校验和
uint8_t calculateChecksum(float *data, uint8_t length) {
  uint8_t cs = 0;
  for (uint8_t i = 0; i < length; i++) {
    uint8_t *bytes = (uint8_t *)&data[i];
    for (uint8_t j = 0; j < sizeof(float); j++) {
      cs ^= bytes[j];
    }
  }
  return cs;
}

void setup() {
  Serial.begin(19200); // 初始化串口，波特率同原来设定
  Wire.begin(4, 5);    // I2C 接口，SDA=4, SCL=5

  // 初始化 BME280
  while (!bme.begin(0x76, &Wire)) {
    Serial.println("Could not find a valid BME280 sensor.");
    delay(500);
  }
  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::SAMPLING_X1,
                  Adafruit_BME280::FILTER_OFF);
}

void loop() {
  unsigned long now = millis();
  if (now - lastMeasure >= 60000) { // 每 60 秒测量一次
    lastMeasure = now;

    // 强制测量
    bme.takeForcedMeasurement();

    // 临时存放浮点数据用于校验
    float buf[3];
    buf[0] = bme.readTemperature();
    buf[1] = bme.readHumidity();
    buf[2] = bme.readPressure() / 100.0F;

    // 计算校验和
    uint8_t cs = calculateChecksum(buf, 3);

    // 准备发送的数据包
    sensor_st packet;
    packet.temperature = buf[0];
    packet.humidity = buf[1];
    packet.pressure = buf[2];
    packet.checksum = cs;

    // 通过串口发送：先同步字节，再发送整个结构体的二进制内容
    Serial.write(SYNC_WORD);
    Serial.write((uint8_t *)&packet, sizeof(packet));
  }
}
