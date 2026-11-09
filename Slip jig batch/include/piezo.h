#pragma once
#include "sensor.h"

// Piezo vibration sensor read through the ESP32 ADC.
// Sampled at PIEZO_SAMPLE_RATE_HZ using a fixed-period schedule.
class PiezoSensor : public SensorT<1> {
public:
  PiezoSensor() : SensorT<1>("piezo") {}

  bool begin() override;
  void update(uint32_t nowUs) override;

protected:
  void onArm(uint32_t t0Us) override;
  void printMeta(Print& out) const override;
  const char* channelName(uint8_t) const override { return "value"; }

private:
  uint32_t periodUs_ = 1000000UL / PIEZO_SAMPLE_RATE_HZ;
  uint32_t nextDueUs_ = 0;
};