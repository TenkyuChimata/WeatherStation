# STM32 High-Precision Environmental Monitoring Station

A high-precision environmental monitoring station based on **STM32 + PlatformIO + Arduino framework**, integrating:

- 🌡 **SHT85** – temperature & humidity
- 🌬 **BMP390L** – high-resolution barometric pressure
- 🌫 **Sensirion SPS30** – particulate matter (PM1.0 / PM2.5 / PM4.0 / PM10)
- ☢ **Geiger counter** – real-time radiation monitoring
- 🔗 **Binary serial protocol** with checksum & sync word

Designed for **long-term unattended operation**, high stability, and easy integration with SBCs / servers.

---

## ✨ Features

- High-accuracy environmental sensing (industrial-grade sensors)
- UART-based SPS30 with **automatic fault detection & recovery**
- Interrupt-driven Geiger counter pulse counting
- Fixed-period logging with **CPM → µSv/h conversion**
- Compact binary output (low bandwidth, low latency)
- PlatformIO-based, reproducible build environment
- Suitable for meteorological, radiation, and environmental monitoring projects

---

## 🧰 Hardware Requirements

### Core MCU

- STM32 (tested on STM32F1 series, e.g. **Blue Pill / STM32F103**)

### Sensors

| Sensor      | Interface         | Notes                       |
| ----------- | ----------------- | --------------------------- |
| SHT85       | I²C               | High accuracy temp & RH     |
| BMP390L     | I²C               | Pressure oversampling ×32   |
| SPS30       | UART (115200 8N1) | PM sensor (UART mode)       |
| Geiger Tube | GPIO interrupt    | Falling-edge pulse counting |

---

## 🔌 Pin Mapping (Default)

### I²C

| Signal | Pin |
| ------ | --- |
| SDA    | PB7 |
| SCL    | PB6 |

### SPS30 (UART)

| SPS30 | STM32 |
| ----- | ----- |
| TX    | PA3   |
| RX    | PA2   |

```cpp
HardwareSerial Serial2(PA3, PA2);
```

### Geiger Counter

| Signal | Pin        |
| ------ | ---------- |
| Pulse  | PA0 (EXTI) |

---

## 📦 Software Stack

- PlatformIO
- Arduino framework for STM32
- Libraries:
  - SHTSensor
  - Adafruit_BMP3XX
  - SensirionUartSps30

---

## ⏱ Sampling & Timing

| Item          | Value   |
| ------------- | ------- |
| Log period    | 60 s    |
| SPS30 warm-up | ~1.2 s  |
| I²C clock     | 100 kHz |
| UART timeout  | 5 s     |

---

## 📡 Serial Output Protocol

Binary stream over USB Serial (Serial):

Sync word:
0x8A

Payload structure:
float data[8] + uint8_t checksum

Data layout:
0 Temperature (°C)  
1 Humidity (%RH)  
2 Pressure (hPa)  
3 Radiation (µSv/h)  
4 PM1.0 (µg/m³)  
5 PM2.5 (µg/m³)  
6 PM4.0 (µg/m³)  
7 PM10 (µg/m³)

Checksum:
XOR of all payload bytes (float array only).

---

## ☢ Radiation Calculation

µSv/h = CPM / 153.8

Note: conversion factor depends on Geiger tube model.

---

## 🛠 SPS30 Reliability Strategy

- Automatic retry on read failure
- Consecutive failure detection
- Automatic stop/start reinitialization
- Cool-down recovery window
