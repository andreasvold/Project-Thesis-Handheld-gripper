#pragma once

#include <Arduino.h>

// Settings for the capacitive taxel readout.
struct CapSensorConfig {
  uint8_t  sensePin = A0;    // reads node B (op-amp output)
  uint16_t exciteHz = 500;   // square-wave frequency on D9 (16 Hz - 50 kHz)
};

// Drives the excitation square wave and reads node B directly.
//
// The excitation runs on Timer1 in hardware, so it is fixed to pin D9
// (OC1A on the Uno) and keeps running steadily while the ADC samples.
// No demodulation or filtering is done: read() and capture() return
// the raw ADC values (0-1023) at node B.
class CapSensor {
public:
  explicit CapSensor(const CapSensorConfig& cfg = CapSensorConfig());

  // Configure pins and start the excitation. Call once in setup().
  void begin();

  void startExcitation();
  void stopExcitation();     // D9 held low
  bool excitationRunning() const { return running_; }

  // Actual excitation frequency after rounding to the timer's steps.
  float exciteHz() const;

  // One raw sample of node B (0-1023).
  int read();

  // Take n back-to-back raw samples of node B.
  // levels (optional, may be nullptr) receives the D9 state (0/1)
  // at each sample, so the waveform can be lined up with the excitation.
  // Returns the average time between samples in microseconds.
  float capture(uint16_t* samples, uint8_t* levels, uint16_t n);

private:
  CapSensorConfig cfg_;
  uint16_t        ocr_;
  bool            running_;
};