#include <Wire.h>
#include <Arduino.h>
#include <SHTSensor.h>
#include <Adafruit_BMP3XX.h>
#include <SensirionI2cSps30.h>

#define SYNC_WORD 0x8A
#define LOG_PERIOD 60000
#define MAX_PERIOD 60000

#ifdef NO_ERROR
#undef NO_ERROR
#endif
#define NO_ERROR 0

#define DATA_FLOATS 7

typedef struct __attribute__((packed)) {
  float data[DATA_FLOATS];
  uint8_t checksum;
} sensor_t;

sensor_t data;
SHTSensor sht;
Adafruit_BMP3XX bmp;
SensirionI2cSps30 sps30;

static char spsErrMsg[64];
static int16_t spsErr;

float usv = 0;
volatile unsigned long counts = 0;
unsigned long cpm = 0;
unsigned int multiplier = 0;
unsigned long previousMillis = 0;

void IRAM_ATTR tube_impulse() {
  counts++;
}

uint8_t checksum_bytes(const uint8_t *buf, size_t len) {
  uint8_t sum = 0;
  for (size_t i = 0; i < len; i++) {
    sum ^= buf[i];
  }
  return sum;
}

void setup() {
  Serial.begin(19200);
  Wire.begin();
  Wire.setClock(100000);

  sht.init();
  sht.setAccuracy(SHTSensor::SHT_ACCURACY_HIGH);

  bmp.begin_I2C();
  bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setPressureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_7);
  bmp.setOutputDataRate(BMP3_ODR_1_5_HZ);

  sps30.begin(Wire, SPS30_I2C_ADDR_69);
  sps30.stopMeasurement();
  spsErr = sps30.startMeasurement(SPS30_OUTPUT_FORMAT_OUTPUT_FORMAT_FLOAT);
  if (spsErr != NO_ERROR) {
    errorToString(spsErr, spsErrMsg, sizeof spsErrMsg);
  }

  multiplier = MAX_PERIOD / LOG_PERIOD;
  attachInterrupt(digitalPinToInterrupt(14), tube_impulse, FALLING);
}

void loop() {
  unsigned long currentMillis = millis();
  while (currentMillis - previousMillis >= LOG_PERIOD) {
    previousMillis += LOG_PERIOD;

    sensor_t dat;
    for (int i = 0; i < DATA_FLOATS; i++)
      dat.data[i] = 0.0f;

    if (sht.readSample()) {
      dat.data[0] = sht.getTemperature();
      dat.data[1] = sht.getHumidity();
    }

    if (bmp.performReading()) {
      dat.data[2] = bmp.pressure / 100.0;
    }

    uint16_t dataReadyFlag = 0;
    spsErr = sps30.readDataReadyFlag(dataReadyFlag);
    if (spsErr == NO_ERROR && dataReadyFlag) {
      float mc1p0 = 0, mc2p5 = 0, mc4p0 = 0, mc10p0 = 0;
      float nc0p5 = 0, nc1p0 = 0, nc2p5 = 0, nc4p0 = 0, nc10p0 = 0;
      float typicalParticleSize = 0;
      spsErr = sps30.readMeasurementValuesFloat(mc1p0, mc2p5, mc4p0, mc10p0, nc0p5, nc1p0, nc2p5, nc4p0, nc10p0, typicalParticleSize);
      if (spsErr == NO_ERROR) {
        dat.data[4] = mc1p0;
        dat.data[5] = mc2p5;
        dat.data[6] = mc10p0;
      }
    }

    unsigned long localCounts;
    noInterrupts();
    localCounts = counts;
    counts = 0;
    interrupts();

    cpm = localCounts * multiplier;
    usv = cpm / 153.8;
    dat.data[3] = usv;

    dat.checksum = checksum_bytes((const uint8_t *)dat.data, sizeof(dat.data));

    Serial.write(SYNC_WORD);
    memcpy(&data, &dat, sizeof(sensor_t));
    Serial.write((uint8_t *)&data, sizeof(sensor_t));
    currentMillis = millis();
  }
}
