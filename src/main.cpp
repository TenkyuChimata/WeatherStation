#include <Wire.h>
#include <Arduino.h>
#include <SHTSensor.h>
#include <Adafruit_BMP3XX.h>
#include <SensirionUartSps30.h>

#define SYNC_WORD 0x8A
#define LOG_PERIOD 60000
#define MAX_PERIOD 60000

#ifdef NO_ERROR
#undef NO_ERROR
#endif
#define NO_ERROR 0

#define DATA_FLOATS 8

typedef struct __attribute__((packed))
{
  float data[DATA_FLOATS];
  uint8_t checksum;
} sensor_t;

sensor_t data;
SHTSensor sht;
Adafruit_BMP3XX bmp;
static SensirionUartSps30 sps30;
HardwareSerial Serial2(PA3, PA2);

static char spsErrMsg[64];
static int16_t spsErr;
static bool sps_ok = false;
static uint8_t sps_fail_streak = 0;
static unsigned long sps_last_recover_ms = 0;

float usv = 0;
volatile uint32_t counts = 0;
uint32_t cpm = 0;
unsigned int multiplier = 0;
unsigned long previousMillis = 0;

void tube_impulse()
{
  counts++;
}

uint8_t checksum_bytes(const uint8_t *buf, size_t len)
{
  uint8_t sum = 0;
  for (size_t i = 0; i < len; i++)
  {
    sum ^= buf[i];
  }
  return sum;
}

static int16_t sps30_read_retry(float &mc1p0, float &mc2p5, float &mc4p0, float &mc10p0,
                                float &nc0p5, float &nc1p0, float &nc2p5, float &nc4p0, float &nc10p0,
                                float &typicalParticleSize)
{
  int16_t e = sps30.readMeasurementValuesFloat(mc1p0, mc2p5, mc4p0, mc10p0,
                                               nc0p5, nc1p0, nc2p5, nc4p0, nc10p0,
                                               typicalParticleSize);
  if (e == NO_ERROR)
    return e;
  delay(80);
  return sps30.readMeasurementValuesFloat(mc1p0, mc2p5, mc4p0, mc10p0,
                                          nc0p5, nc1p0, nc2p5, nc4p0, nc10p0,
                                          typicalParticleSize);
}

void setup()
{
  Serial.begin(115200);
  Wire.setSDA(PB7);
  Wire.setSCL(PB6);
  Wire.begin();
  Wire.setClock(100000);

  sht.init();
  sht.setAccuracy(SHTSensor::SHT_ACCURACY_HIGH);

  bmp.begin_I2C();
  bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setPressureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_7);
  bmp.setOutputDataRate(BMP3_ODR_1_5_HZ);

  Serial2.begin(115200, SERIAL_8N1);
  Serial2.setTimeout(5000);
  sps30.begin(Serial2);
  spsErr = sps30.stopMeasurement();
  delay(100);
  spsErr = sps30.startMeasurement(SPS30_OUTPUT_FORMAT_OUTPUT_FORMAT_FLOAT);
  if (spsErr != NO_ERROR)
  {
    delay(200);
    spsErr = sps30.startMeasurement(SPS30_OUTPUT_FORMAT_OUTPUT_FORMAT_FLOAT);
  }
  sps_ok = (spsErr == NO_ERROR);
  delay(1200);

  multiplier = MAX_PERIOD / LOG_PERIOD;
  pinMode(PA0, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PA0), tube_impulse, FALLING);
  delay(1000);
}

void loop()
{
  unsigned long currentMillis = millis();
  while (currentMillis - previousMillis >= LOG_PERIOD)
  {
    previousMillis += LOG_PERIOD;

    sensor_t dat = {};

    if (sht.readSample())
    {
      dat.data[0] = sht.getTemperature();
      dat.data[1] = sht.getHumidity();
    }

    if (bmp.performReading())
    {
      dat.data[2] = bmp.pressure / 100.0;
    }

    float mc1p0 = 0, mc2p5 = 0, mc4p0 = 0, mc10p0 = 0;
    float nc0p5 = 0, nc1p0 = 0, nc2p5 = 0, nc4p0 = 0, nc10p0 = 0;
    float typicalParticleSize = 0;

    if (!sps_ok)
    {
      if (millis() - sps_last_recover_ms > 3000)
      {
        sps_last_recover_ms = millis();
        (void)sps30.stopMeasurement();
        delay(100);
        spsErr = sps30.startMeasurement(SPS30_OUTPUT_FORMAT_OUTPUT_FORMAT_FLOAT);
        if (spsErr == NO_ERROR)
        {
          sps_ok = true;
          sps_fail_streak = 0;
          delay(1200);
        }
      }
    }

    if (sps_ok)
    {
      spsErr = sps30_read_retry(
          mc1p0, mc2p5, mc4p0, mc10p0,
          nc0p5, nc1p0, nc2p5, nc4p0, nc10p0,
          typicalParticleSize);
    }
    else
    {
      spsErr = (int16_t)1;
    }

    if (spsErr == NO_ERROR)
    {
      dat.data[4] = mc1p0;
      dat.data[5] = mc2p5;
      dat.data[6] = mc4p0;
      dat.data[7] = mc10p0;
      sps_fail_streak = 0;
    }
    else
    {
      if (sps_ok && sps_fail_streak < 255)
        sps_fail_streak++;
      if (sps_ok && sps_fail_streak >= 5)
        sps_ok = false;
    }

    uint32_t localCounts;
    noInterrupts();
    localCounts = counts;
    counts = 0;
    interrupts();

    cpm = localCounts * multiplier;
    usv = cpm / 153.8;
    dat.data[3] = usv;

    dat.checksum = checksum_bytes((const uint8_t *)dat.data, sizeof(dat.data));

    uint8_t sync = SYNC_WORD;
    Serial.write(&sync, 1);
    Serial.write((uint8_t *)&dat, sizeof(sensor_t));
    currentMillis = millis();
  }
}
