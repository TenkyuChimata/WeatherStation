#include <SPI.h>
#include <Arduino.h>
#include <SHTSensor.h>
#include <ESP8266WiFi.h>
#include <Adafruit_BMP3XX.h>
#include <ESP8266WebServer.h>

#define SYNC_WORD 0x8A
#define LOG_PERIOD 60000
#define MAX_PERIOD 60000

const char* ssid = "";
const char* password = "";

typedef struct {
    float data[4];
    uint8_t checksum;
} sensor_t;

sensor_t data;
SHTSensor sht;
Adafruit_BMP3XX bmp;
ESP8266WebServer server(80);
float usv = 0;
unsigned long counts = 0;
unsigned long cpm = 0;
unsigned int multiplier = 0;
unsigned long previousMillis = 0;

void IRAM_ATTR tube_impulse() {
  counts++;
}

uint8_t checksum(float* data, uint8_t length) {
  uint8_t checksum = 0;
  for (uint8_t i = 0; i < length; i++) {
      uint8_t* bytes = (uint8_t*)&data[i];

      for (uint8_t j = 0; j < sizeof(float); j++) {
          checksum ^= bytes[j];
      }
  }
  return checksum;
}

void setup() {
  Wire.begin();
  sht.init();
  sht.setAccuracy(SHTSensor::SHT_ACCURACY_HIGH);
  bmp.begin_I2C();
  bmp.setTemperatureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setPressureOversampling(BMP3_OVERSAMPLING_32X);
  bmp.setIIRFilterCoeff(BMP3_IIR_FILTER_COEFF_1);
  bmp.setOutputDataRate(BMP3_ODR_200_HZ);
  multiplier = MAX_PERIOD / LOG_PERIOD;
  Serial.begin(19200);
  attachInterrupt(14, tube_impulse, FALLING);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  server.on("/", HTTP_GET, []() {
    char buffer[256];
    snprintf(buffer, sizeof(buffer), "{\"temperature\": %f, \"humidity\": %f, \"pressure\": %f, \"usv\": %f}", data.data[0], data.data[1], data.data[2], data.data[3]);
    server.send(200, "application/json", buffer);
  });
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
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis > LOG_PERIOD) {
    previousMillis = currentMillis;
    sensor_t dat;

    if (sht.readSample()) {
      dat.data[0] = sht.getTemperature();
      dat.data[1] = sht.getHumidity();
    }

    if (bmp.performReading()) {
      dat.data[2] = bmp.pressure / 100.0;
    }

    if (dat.data[2] < 0 || counts == 0) {
      ESP.reset();
    }

    cpm = counts * multiplier;
    usv = cpm / 153.8;
    dat.data[3] = usv;

    dat.checksum = checksum(dat.data, 4);
    Serial.write(SYNC_WORD);
    delayMicroseconds(10);
    memcpy(&data, &dat, sizeof(sensor_t));
    Serial.write((uint8_t*)&data, sizeof(sensor_t));
    Serial.flush();
    counts = 0;
  }
}
