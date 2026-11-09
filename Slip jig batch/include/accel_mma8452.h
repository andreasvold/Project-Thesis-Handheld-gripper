#pragma once
#include "sensor.h"

// MMA8452Q / MMA8451Q 3-axis accelerometer over I2C.
// Sampled at its own output data rate (ACCEL_ODR); the driver polls the
// data-ready flag and records each new sample with a timestamp.
class AccelMMA8452 : public SensorT<3> {
public:
  AccelMMA8452() : SensorT<3>("accel") {}

  bool begin() override;
  void update(uint32_t nowUs) override;

protected:
  void onArm(uint32_t t0Us) override;
  void printMeta(Print& out) const override;
  const char* channelName(uint8_t c) const override;

private:
  uint8_t readReg(uint8_t reg);
  void writeReg(uint8_t reg, uint8_t val);

  float    odrHz_ = 0.0f;
  uint32_t periodUs_ = 0;
  uint32_t pollIntervalUs_ = 0;
  uint32_t nextPollUs_ = 0;
  uint8_t  shift_ = 4;          // 4 = 12-bit (MMA8452Q), 2 = 14-bit (MMA8451Q)
  uint16_t countsPerG_ = 1024;
  uint8_t  rangeG_ = 2;
};