#pragma once
#include "sensor.h"

// Charge-amplifier capacitance sensor. Each sample is the unscaled result of
// one complete two-polarity measurement cycle.
class CapacitanceSensor : public SensorT<1> {
public:
  CapacitanceSensor() : SensorT<1>("capacitance") {}

  bool begin() override;
  void update(uint32_t nowUs) override;

protected:
  void onArm(uint32_t t0Us) override;
  void printMeta(Print& out) const override;
  const char* channelName(uint8_t) const override { return "raw_cycle"; }

private:
  struct Biquad {
    float b0 = 0.0f;
    float b1 = 0.0f;
    float b2 = 0.0f;
    float a1 = 0.0f;
    float a2 = 0.0f;
    float x1 = 0.0f;
    float x2 = 0.0f;
    float y1 = 0.0f;
    float y2 = 0.0f;

    float process(float input);
    void reset();
  };

  void driveState(bool csHigh);
  void pulseReset();
  int32_t rawCycle();
  void configureBiquad(Biquad& filter, bool highPass, float cutoffHz,
                       float prototypeA1, float prototypeA2);

  uint32_t periodUs_ = 1000000UL / CAPACITANCE_SAMPLE_RATE_HZ;
  uint32_t nextDueUs_ = 0;
  Biquad highPassFilter_;
  Biquad lowPassFilter_;
};
