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
  void driveState(bool csHigh);
  void pulseReset();
  int32_t rawCycle();

  uint32_t periodUs_ = 1000000UL / CAPACITANCE_SAMPLE_RATE_HZ;
  uint32_t nextDueUs_ = 0;
};
