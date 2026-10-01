#include "CapSensor.h"

CapSensor::CapSensor(const CapSensorConfig& cfg)
  : cfg_(cfg), out_(nullptr), mask_(0), baseline_(0.0f) {}

void CapSensor::begin() {
  pinMode(cfg_.excitePin, OUTPUT);
  digitalWrite(cfg_.excitePin, LOW);

  // Cache the port register and bit so edges are fast and consistent
  // (digitalWrite takes several microseconds and varies).
  out_  = portOutputRegister(digitalPinToPort(cfg_.excitePin));
  mask_ = digitalPinToBitMask(cfg_.excitePin);

  // First conversion after power-up is often off; discard it.
  analogRead(cfg_.sensePin);
}

inline void CapSensor::exciteHigh() { *out_ |= mask_; }
inline void CapSensor::exciteLow()  { *out_ &= ~mask_; }

float CapSensor::measure() {
  long sum = 0;

  for (uint16_t i = 0; i < cfg_.cycles; i++) {
    exciteHigh();
    delayMicroseconds(cfg_.settleUs);
    int hi = analogRead(cfg_.sensePin);   // just after rising edge
    delayMicroseconds(cfg_.holdUs);

    exciteLow();
    delayMicroseconds(cfg_.settleUs);
    int lo = analogRead(cfg_.sensePin);   // just after falling edge
    delayMicroseconds(cfg_.holdUs);

    sum += hi - lo;                       // multiply by +1 / -1
  }

  return (float)sum / cfg_.cycles;        // average = low-pass filter
}

float CapSensor::calibrate(uint8_t samples) {
  if (samples == 0) samples = 1;
  float sum = 0.0f;
  for (uint8_t i = 0; i < samples; i++) sum += measure();
  baseline_ = sum / samples;
  return baseline_;
}