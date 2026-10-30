#include <Arduino.h>
#include <Wire.h>

const uint8_t ADDR = 0x1D;      // 0x1C if SA0 is grounded

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  Wire.setClock(400000);    // fast I2C so no samples are missed at 800 Hz
  digitalWrite(SDA, LOW);   // turn off the Uno's 5 V pull-ups (sensor is 3.3 V)
  digitalWrite(SCL, LOW);

  writeReg(0x2A, 0x00);     // standby, so settings can be changed
  writeReg(0x0E, 0x10);     // ±2 g, high-pass filter on (use 0x00 to keep gravity)
  writeReg(0x2A, 0x01);     // 800 Hz, active
}

void loop() {
  // Read status + X, Y, Z in one go (registers 0x00 to 0x06)
  Wire.beginTransmission(ADDR);
  Wire.write(0x00);
  Wire.endTransmission(false);    // repeated start (the chip requires it)
  Wire.requestFrom(ADDR, (uint8_t)7);
  uint8_t b[7];
  for (uint8_t i = 0; i < 7; i++) b[i] = Wire.read();

  if (b[0] & 0x04) {              // a new Z sample is ready
    int16_t z = (b[5] << 8) | b[6];
    Serial.println(z >> 4);       // raw counts, 1024 counts = 1 g
  }
}