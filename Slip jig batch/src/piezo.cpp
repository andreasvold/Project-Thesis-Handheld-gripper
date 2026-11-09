#include "piezo.h"

bool PiezoSensor::begin() {
  analogReadResolution(PIEZO_ADC_BITS);
  pinMode(PIEZO_PIN, INPUT);
  return true;                       // internal ADC: nothing to detect
}

void PiezoSensor::onArm(uint32_t t0Us) {
  nextDueUs_ = t0Us;
}

void PiezoSensor::update(uint32_t nowUs) {
  if (!recording()) return;
  if ((int32_t)(nowUs - nextDueUs_) < 0) return;     // not due yet

  int16_t v = (int16_t)analogRead(PIEZO_PIN);
  record(nowUs, &v);

  // Move to the next slot after now. Every slot we jumped over is a missed sample.
  nextDueUs_ += periodUs_;
  while ((int32_t)(nowUs - nextDueUs_) >= 0) {
    nextDueUs_ += periodUs_;
    missed_++;
  }
}

void PiezoSensor::printMeta(Print& out) const {
  constexpr float fullScale = (float)((1u << PIEZO_ADC_BITS) - 1);
  out.print(F(" rate_hz=")); out.print(PIEZO_SAMPLE_RATE_HZ);
  out.print(F(" adc_bits=")); out.print(PIEZO_ADC_BITS);
  out.print(F(" scale=")); out.print(PIEZO_VREF_V / fullScale, 10);
  out.print(F(" unit=V"));
}