#pragma once

#include <Arduino.h>

// Settings for one capacitive taxel channel.
struct CapSensorConfig {
  uint8_t  excitePin = 9;    // drives C_ref with a square wave
  uint8_t  sensePin  = A0;   // reads node B (op-amp output, pin 6)
  uint16_t settleUs  = 5;    // wait after each edge before sampling
  uint16_t holdUs    = 300;  // time spent in each half-cycle after sampling
  uint16_t cycles    = 64;   // cycles averaged per measurement
};

// Synchronous (software) demodulation of a capacitive divider.
//
// Each cycle the class drives the excitation pin high, samples node B
// just after the rising edge, drives it low, samples just after the
// falling edge, and accumulates (high - low). Averaging over many cycles
// acts as the low-pass filter: slow drift and mains hum appear in both
// samples and cancel, while the step caused by the excitation remains.
class CapSensor {
public:
  explicit CapSensor(const CapSensorConfig& cfg = CapSensorConfig());

  // Configure pins. Call once in setup().
  void begin();

  // One measurement: average step size in ADC counts.
  float measure();

  // Average several measurements with the sensor untouched and store
  // the result as the baseline. Returns the baseline.
  float calibrate(uint8_t samples = 16);

  float baseline() const { return baseline_; }

  // Reading minus baseline.
  float delta(float reading) const { return reading - baseline_; }

  void setCycles(uint16_t cycles) { cfg_.cycles = cycles ? cycles : 1; }
  const CapSensorConfig& config() const { return cfg_; }

private:
  void exciteHigh();
  void exciteLow();

  CapSensorConfig   cfg_;
  volatile uint8_t* out_;
  uint8_t           mask_;
  float             baseline_;
};