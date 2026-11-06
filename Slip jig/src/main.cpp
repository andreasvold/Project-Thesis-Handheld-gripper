#include <Arduino.h>
#include <Wire.h>

constexpr uint8_t ADDR            = 0x1D;  // 0x1C if SA0 is grounded
constexpr uint8_t REG_STATUS      = 0x00;
constexpr uint8_t REG_WHO_AM_I    = 0x0D;
constexpr uint8_t REG_XYZ_DATA_CFG = 0x0E;
constexpr uint8_t REG_CTRL1       = 0x2A;
constexpr uint8_t PIEZO_PIN       = A0;

// 12-bit (MMA8452Q) -> shift 4, 14-bit (MMA8451Q) -> shift 2
uint8_t dataShift = 4;

// Piezo tracking between accelerometer samples
int piezoLast = 0;
int piezoMin  = 1023;
int piezoMax  = 0;

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

uint8_t readReg(uint8_t reg) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(ADDR, (uint8_t)1);
  return Wire.available() ? Wire.read() : 0xFF;
}

void setup() {
  Serial.begin(250000);
  Wire.begin();
  Wire.setClock(400000);

  uint8_t id = readReg(REG_WHO_AM_I);
  if (id == 0x1A) dataShift = 2;            // MMA8451Q
  else if (id != 0x2A) {                    // MMA8452Q = 0x2A
    Serial.print(F("Unexpected WHO_AM_I: 0x"));
    Serial.println(id, HEX);
  }

  writeReg(REG_CTRL1, 0x00);                // Standby to change settings
  writeReg(REG_XYZ_DATA_CFG, 0x10);         // +/-2g, high-pass filter on output
  writeReg(REG_CTRL1, 0x01);                // 800 Hz, active

  Serial.println(F("t_us,ax,ay,az,piezo,piezo_pp"));
}

void loop() {
  // Sample the piezo every pass (much faster than the accelerometer rate)
  int v = analogRead(PIEZO_PIN);
  piezoLast = v;
  if (v < piezoMin) piezoMin = v;
  if (v > piezoMax) piezoMax = v;

  // Read status + XYZ in one burst
  Wire.beginTransmission(ADDR);
  Wire.write(REG_STATUS);
  Wire.endTransmission(false);
  if (Wire.requestFrom(ADDR, (uint8_t)7) != 7) return;

  uint8_t b[7];
  for (uint8_t i = 0; i < 7; i++) b[i] = Wire.read();

  if (!(b[0] & 0x08)) return;               // ZYXDR: new X, Y and Z ready

  int16_t x = (int16_t)((b[1] << 8) | b[2]) >> dataShift;
  int16_t y = (int16_t)((b[3] << 8) | b[4]) >> dataShift;
  int16_t z = (int16_t)((b[5] << 8) | b[6]) >> dataShift;

  Serial.print(micros());  Serial.print(',');
  Serial.print(x);         Serial.print(',');
  Serial.print(y);         Serial.print(',');
  Serial.print(z);         Serial.print(',');
  Serial.print(piezoLast); Serial.print(',');
  Serial.println(piezoMax - piezoMin);

  piezoMin = 1023;
  piezoMax = 0;
}