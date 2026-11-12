#pragma once
#include <Arduino.h>

// =====================================================================
//  GLOBAL
// =====================================================================
constexpr uint32_t SERIAL_BAUD = 115200;      // ignored with native USB CDC

// Samples recorded PER SENSOR in one debug capture.
constexpr uint32_t CAPTURE_SAMPLES = 10000;

// Abort a capture after this long (protects against a sensor that never delivers).
constexpr uint32_t CAPTURE_TIMEOUT_MS = 120000;

// How often the board prints a progress line while recording.
constexpr uint32_t PROGRESS_PERIOD_MS = 1000;

// =====================================================================
//  SENSOR SELECTION
//  false = the sensor is not created: no bus traffic, no RAM reserved.
// =====================================================================
constexpr bool ENABLE_ACCEL = false;
constexpr bool ENABLE_PIEZO = false;
constexpr bool ENABLE_CAPACITANCE = true;

// =====================================================================
//  PINS (ESP32-C6)
// =====================================================================
constexpr uint8_t PIN_SDA   = 4;
constexpr uint8_t PIN_SCL   = 5;
constexpr uint8_t PIEZO_PIN = 1;              // ADC1 channel (C6: GPIO0-GPIO6)
constexpr uint8_t CAPACITANCE_RESET_PIN = 7;
constexpr uint8_t CAPACITANCE_CS_PIN = 10;
constexpr uint8_t CAPACITANCE_CREF_PIN = 11;
constexpr uint8_t CAPACITANCE_ADC_PIN = 2;    // ADC1 channel (C6: GPIO0-GPIO6)

// =====================================================================
//  I2C / ACCELEROMETER (MMA8452Q or MMA8451Q, auto-detected)
// =====================================================================
constexpr uint32_t I2C_CLOCK_HZ   = 400000;
constexpr uint8_t  ACCEL_I2C_ADDR = 0x1D;    // 0x1C if SA0 is grounded

// Output data rate = how often the accelerometer produces a sample.
enum class AccelOdr : uint8_t {
  Hz800 = 0, Hz400, Hz200, Hz100, Hz50, Hz12_5, Hz6_25, Hz1_56
};
constexpr AccelOdr ACCEL_ODR = AccelOdr::Hz400;

// Full-scale range: G2 = +/-2 g, G4 = +/-4 g, G8 = +/-8 g.
enum class AccelRange : uint8_t { G2 = 0, G4 = 1, G8 = 2 };
constexpr AccelRange ACCEL_RANGE = AccelRange::G2;

// High-pass filter on the output: removes DC/gravity, keeps vibration.
constexpr bool ACCEL_HIGH_PASS = true;

// =====================================================================
//  PIEZO (ADC)
// =====================================================================
constexpr uint32_t PIEZO_SAMPLE_RATE_HZ = 10000;   // target rate; check achieved rate with --stats
constexpr uint8_t  PIEZO_ADC_BITS       = 12;
constexpr float    PIEZO_VREF_V         = 3.3f;   // only used to convert counts -> volts in plots

// =====================================================================
//  CAPACITANCE SENSOR (CHARGE AMPLIFIER)
// =====================================================================
constexpr uint32_t CAPACITANCE_SAMPLE_RATE_HZ = 1000;
constexpr uint8_t CAPACITANCE_RESET_US = 5;
constexpr uint8_t CAPACITANCE_SETTLE_US = 5;
constexpr uint8_t CAPACITANCE_ADC_BITS = 12;