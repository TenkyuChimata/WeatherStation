#include <SPI.h>
#include <Arduino.h>
#include <SHTSensor.h>

#define SYNC_WORD 0x8A
#define LOG_PERIOD 60000
#define MAX_PERIOD 60000

typedef struct {
  float data[3];
  uint8_t checksum;
} sensor_t;

sensor_t data;
SHTSensor sht;
float usv = 0;
unsigned long counts = 0;
unsigned long cpm = 0;
unsigned int multiplier = 0;
unsigned long previousMillis = 0;

void IRAM_ATTR tube_impulse() {
  counts++;
}

uint8_t checksum(float *dataArr, uint8_t length) {
  uint8_t sum = 0;
  for (uint8_t i = 0; i < length; i++) {
    uint8_t *bytes = (uint8_t *)&dataArr[i];
    for (uint8_t j = 0; j < sizeof(float); j++) {
      sum ^= bytes[j];
    }
  }
  return sum;
}

void setup() {
  Serial.begin(19200);
  Wire.begin();
  sht.init();
  sht.setAccuracy(SHTSensor::SHT_ACCURACY_HIGH);
  multiplier = MAX_PERIOD / LOG_PERIOD;
  attachInterrupt(14, tube_impulse, FALLING);
}

void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis > LOG_PERIOD) {
    previousMillis = currentMillis;
    sensor_t dat;

    dat.data[0] = 0.0;
    dat.data[1] = 0.0;
    dat.data[2] = 0.0;
    if (sht.readSample()) {
      dat.data[0] = sht.getTemperature();
      dat.data[1] = sht.getHumidity();
    }

    cpm = counts * multiplier;
    usv = cpm / 153.8;
    dat.data[2] = usv;
    dat.checksum = checksum(dat.data, 3);

    Serial.write(SYNC_WORD);
    delayMicroseconds(10);
    memcpy(&data, &dat, sizeof(sensor_t));
    Serial.write((uint8_t *)&data, sizeof(sensor_t));
    Serial.flush();
    counts = 0;
  }
}
