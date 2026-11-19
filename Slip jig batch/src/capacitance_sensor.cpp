#include "capacitance_sensor.h"

#include <math.h>

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

  if (CAPACITANCE_BANDPASS_ENABLED) {
    float prototypeA1 = 1.41421356f;
    float prototypeA2 = 1.0f;
    if (CAPACITANCE_FILTER_TYPE == CapacitanceFilterType::ChebyshevI) {
      const float epsilon = sqrtf(powf(10.0f, CAPACITANCE_CHEBYSHEV_RIPPLE_DB / 10.0f) - 1.0f);
      const float mu = asinhf(1.0f / epsilon) / 2.0f;
      const float sinhMu = sinhf(mu);
      const float coshMu = coshf(mu);
      prototypeA1 = 1.41421356f * sinhMu;
      prototypeA2 = (sinhMu * sinhMu + coshMu * coshMu) / 2.0f;
    }

    configureBiquad(highPassFilter_, true, CAPACITANCE_FILTER_LOW_HZ,
                    prototypeA1, prototypeA2);
    configureBiquad(lowPassFilter_, false, CAPACITANCE_FILTER_HIGH_HZ,
                    prototypeA1, prototypeA2);
  }
  return true;
}

float CapacitanceSensor::Biquad::process(float input) {
  const float output = b0 * input + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
  x2 = x1;
  x1 = input;
  y2 = y1;
  y1 = output;
  return output;
}

void CapacitanceSensor::Biquad::reset() {
  x1 = x2 = y1 = y2 = 0.0f;
}

void CapacitanceSensor::configureBiquad(Biquad& filter, bool highPass,
                                         float cutoffHz, float prototypeA1,
                                         float prototypeA2) {
  const float sampleRate = (float)CAPACITANCE_SAMPLE_RATE_HZ;
  const float angularCutoff = 2.0f * sampleRate *
      tanf(3.14159265f * cutoffHz / sampleRate);
  const float bilinear = 2.0f * sampleRate;
  float denominator0;
  float denominator1;
  float denominator2;

  if (highPass) {
    const float a1 = prototypeA1 * angularCutoff / prototypeA2;
    const float a2 = angularCutoff * angularCutoff / prototypeA2;
    denominator0 = bilinear * bilinear + a1 * bilinear + a2;
    denominator1 = -2.0f * bilinear * bilinear + 2.0f * a2;
    denominator2 = bilinear * bilinear - a1 * bilinear + a2;
    filter.b0 = bilinear * bilinear / denominator0;
    filter.b1 = -2.0f * filter.b0;
    filter.b2 = filter.b0;
  } else {
    const float a1 = prototypeA1 * angularCutoff;
    const float a2 = prototypeA2 * angularCutoff * angularCutoff;
    denominator0 = bilinear * bilinear + a1 * bilinear + a2;
    denominator1 = -2.0f * bilinear * bilinear + 2.0f * a2;
    denominator2 = bilinear * bilinear - a1 * bilinear + a2;
    const float numerator = a2 / denominator0;
    filter.b0 = numerator;
    filter.b1 = 2.0f * numerator;
    filter.b2 = numerator;
  }

  filter.a1 = denominator1 / denominator0;
  filter.a2 = denominator2 / denominator0;
  filter.reset();
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
  highPassFilter_.reset();
  lowPassFilter_.reset();
}

void CapacitanceSensor::update(uint32_t nowUs) {
  if (!recording()) return;
  if ((int32_t)(nowUs - nextDueUs_) < 0) return;

  float sample = (float)rawCycle();
  if (CAPACITANCE_BANDPASS_ENABLED) {
    sample = lowPassFilter_.process(highPassFilter_.process(sample));
  }
  if (sample > 32767.0f) sample = 32767.0f;
  if (sample < -32768.0f) sample = -32768.0f;
  const int16_t value = (int16_t)(sample >= 0.0f ? sample + 0.5f : sample - 0.5f);
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
