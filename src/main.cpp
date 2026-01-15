#include <SPI.h>
#include <Arduino.h>
#include <SHTSensor.h>
#include <Adafruit_BMP3XX.h>

#define SYNC_WORD 0x8A
#define LOG_PERIOD 60000
#define MAX_PERIOD 60000

typedef struct __attribute__((packed)) {
  float data[4];
  uint8_t checksum;
} sensor_t;

sensor_t data;
SHTSensor sht;
Adafruit_BMP3XX bmp;

float usv = 0;
volatile unsigned long counts = 0;
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

  bmp.begin_I2C();
  bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setPressureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_7);
  bmp.setOutputDataRate(BMP3_ODR_1_5_HZ);

  multiplier = MAX_PERIOD / LOG_PERIOD;
  attachInterrupt(digitalPinToInterrupt(14), tube_impulse, FALLING);
}

void loop() {
  unsigned long currentMillis = millis();
  while (currentMillis - previousMillis >= LOG_PERIOD) {
    previousMillis += LOG_PERIOD;

    sensor_t dat;
    dat.data[0] = 0.0;
    dat.data[1] = 0.0;
    dat.data[2] = 0.0;
    dat.data[3] = 0.0;

    if (sht.readSample()) {
      dat.data[0] = sht.getTemperature();
      dat.data[1] = sht.getHumidity();
    }

    if (bmp.performReading()) {
      dat.data[2] = bmp.pressure / 100.0;
    }

    unsigned long localCounts;
    noInterrupts();
    localCounts = counts;
    counts = 0;
    interrupts();

    cpm = localCounts * multiplier;
    usv = cpm / 153.8;
    dat.data[3] = usv;

    dat.checksum = checksum(dat.data, 4);

    Serial.write(SYNC_WORD);
    memcpy(&data, &dat, sizeof(sensor_t));
    Serial.write((uint8_t *)&data, sizeof(sensor_t));
    currentMillis = millis();
  }
}
