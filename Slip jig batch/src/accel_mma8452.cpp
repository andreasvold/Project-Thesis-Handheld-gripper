#include "accel_mma8452.h"
#include <Wire.h>

namespace {
constexpr uint8_t REG_STATUS       = 0x00;
constexpr uint8_t REG_OUT_X_MSB    = 0x01;
constexpr uint8_t REG_WHO_AM_I     = 0x0D;
constexpr uint8_t REG_XYZ_DATA_CFG = 0x0E;
constexpr uint8_t REG_CTRL1        = 0x2A;

constexpr uint8_t WHO_MMA8452Q = 0x2A;        // 12-bit
constexpr uint8_t WHO_MMA8451Q = 0x1A;        // 14-bit

constexpr uint8_t STATUS_ZYXDR = 0x08;        // new X/Y/Z sample ready
constexpr uint8_t STATUS_ZYXOW = 0x80;        // a sample was overwritten unread

// Indexed by AccelOdr (value = DR bits in CTRL_REG1)
constexpr float ODR_HZ[8] = {800.0f, 400.0f, 200.0f, 100.0f, 50.0f, 12.5f, 6.25f, 1.5625f};
}

uint8_t AccelMMA8452::readReg(uint8_t reg) {
  Wire.beginTransmission(ACCEL_I2C_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  if (Wire.requestFrom(ACCEL_I2C_ADDR, (uint8_t)1) != 1) return 0xFF;
  return Wire.read();
}

void AccelMMA8452::writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(ACCEL_I2C_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool AccelMMA8452::begin() {
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(I2C_CLOCK_HZ);

  uint8_t id = readReg(REG_WHO_AM_I);
  uint16_t baseCounts = 0;
  if (id == WHO_MMA8452Q)      { shift_ = 4; baseCounts = 1024; }  // counts/g at 2 g
  else if (id == WHO_MMA8451Q) { shift_ = 2; baseCounts = 4096; }
  else return false;                                               // not found

  rangeG_     = 2 << (uint8_t)ACCEL_RANGE;                         // 2, 4 or 8
  countsPerG_ = baseCounts >> (uint8_t)ACCEL_RANGE;

  writeReg(REG_CTRL1, 0x00);                                       // standby while configuring
  writeReg(REG_XYZ_DATA_CFG, (ACCEL_HIGH_PASS ? 0x10 : 0x00) | (uint8_t)ACCEL_RANGE);
  writeReg(REG_CTRL1, (uint8_t)(((uint8_t)ACCEL_ODR) << 3) | 0x01);  // DR bits + ACTIVE

  odrHz_    = ODR_HZ[(uint8_t)ACCEL_ODR];
  periodUs_ = (uint32_t)(1000000.0f / odrHz_);

  // Poll the status register about 4x per sample period, clamped to 100..2000 us.
  uint32_t poll = periodUs_ / 4;
  if (poll < 100)  poll = 100;
  if (poll > 2000) poll = 2000;
  pollIntervalUs_ = poll;
  return true;
}

void AccelMMA8452::onArm(uint32_t t0Us) {
  nextPollUs_ = t0Us;
}

void AccelMMA8452::update(uint32_t nowUs) {
  if (!recording()) return;
  if ((int32_t)(nowUs - nextPollUs_) < 0) return;      // throttle I2C polling
  nextPollUs_ = nowUs + pollIntervalUs_;

  uint8_t status = readReg(REG_STATUS);
  if (!(status & STATUS_ZYXDR)) return;                 // no new sample yet
  if (status & STATUS_ZYXOW) overwritten_++;            // we were too slow for the ODR

  Wire.beginTransmission(ACCEL_I2C_ADDR);
  Wire.write(REG_OUT_X_MSB);
  Wire.endTransmission(false);
  if (Wire.requestFrom(ACCEL_I2C_ADDR, (uint8_t)6) != 6) return;

  uint8_t b[6];
  for (uint8_t i = 0; i < 6; i++) b[i] = Wire.read();

  int16_t v[3];
  for (uint8_t axis = 0; axis < 3; axis++) {
    int16_t raw = (int16_t)((b[2 * axis] << 8) | b[2 * axis + 1]);
    v[axis] = raw >> shift_;
  }
  record(nowUs, v);
}

void AccelMMA8452::printMeta(Print& out) const {
  out.print(F(" rate_hz=")); out.print(odrHz_, 3);
  out.print(F(" range_g=")); out.print(rangeG_);
  out.print(F(" hpf=")); out.print(ACCEL_HIGH_PASS ? 1 : 0);
  out.print(F(" scale=")); out.print(1.0 / countsPerG_, 10);
  out.print(F(" unit=g"));
}

const char* AccelMMA8452::channelName(uint8_t c) const {
  static const char* const names[] = {"ax", "ay", "az"};
  return names[c];
}