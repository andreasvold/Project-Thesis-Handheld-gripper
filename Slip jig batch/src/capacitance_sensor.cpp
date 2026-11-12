#include "capacitance_sensor.h"

bool CapacitanceSensor::begin() {
  analogReadResolution(CAPACITANCE_ADC_BITS);
  analogSetPinAttenuation(CAPACITANCE_ADC_PIN, ADC_11db);

  pinMode(CAPACITANCE_RESET_PIN, OUTPUT);
  pinMode(CAPACITANCE_CS_PIN, OUTPUT);
  pinMode(CAPACITANCE_CREF_PIN, OUTPUT);
  pinMode(CAPACITANCE_ADC_PIN, INPUT);

  digitalWrite(CAPACITANCE_RESET_PIN, LOW);
  driveState(false);
  analogRead(CAPACITANCE_ADC_PIN); // Discard the first conversion.
  return true;
}

void CapacitanceSensor::driveState(bool csHigh) {
  digitalWrite(CAPACITANCE_CS_PIN, csHigh ? HIGH : LOW);
  digitalWrite(CAPACITANCE_CREF_PIN, csHigh ? LOW : HIGH);
}

void CapacitanceSensor::pulseReset() {
  digitalWrite(CAPACITANCE_RESET_PIN, HIGH);
  delayMicroseconds(CAPACITANCE_RESET_US);
  digitalWrite(CAPACITANCE_RESET_PIN, LOW);
  delayMicroseconds(CAPACITANCE_SETTLE_US);
}

int32_t CapacitanceSensor::rawCycle() {
  driveState(false);
  pulseReset();
  const int16_t rA0 = analogRead(CAPACITANCE_ADC_PIN);
  driveState(true);
  delayMicroseconds(CAPACITANCE_SETTLE_US);
  const int16_t rA1 = analogRead(CAPACITANCE_ADC_PIN);

  pulseReset();
  const int16_t rB0 = analogRead(CAPACITANCE_ADC_PIN);
  driveState(false);
  delayMicroseconds(CAPACITANCE_SETTLE_US);
  const int16_t rB1 = analogRead(CAPACITANCE_ADC_PIN);

  const int32_t stepA = (int32_t)rA1 - rA0;
  const int32_t stepB = (int32_t)rB1 - rB0;
  return stepB - stepA;
}

void CapacitanceSensor::onArm(uint32_t t0Us) {
  nextDueUs_ = t0Us;
}

void CapacitanceSensor::update(uint32_t nowUs) {
  if (!recording()) return;
  if ((int32_t)(nowUs - nextDueUs_) < 0) return;

  const int16_t value = (int16_t)rawCycle();
  record(nowUs, &value);

  const uint32_t completedUs = micros();
  nextDueUs_ += periodUs_;
  while ((int32_t)(completedUs - nextDueUs_) >= 0) {
    nextDueUs_ += periodUs_;
    missed_++;
  }
}

void CapacitanceSensor::printMeta(Print& out) const {
  out.print(F(" rate_hz=")); out.print(CAPACITANCE_SAMPLE_RATE_HZ);
  out.print(F(" adc_bits=")); out.print(CAPACITANCE_ADC_BITS);
  out.print(F(" scale=1 unit=adc_counts"));
}
