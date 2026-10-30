#include <Arduino.h>
#include <Wire.h>

const uint8_t ADDR = 0x1D; // 0x1C if SA0 is grounded

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(250000);
  Wire.begin();
  Wire.setClock(400000);    // Fast I2C (400 kHz) for 800 Hz sampling
  
  pinMode(SDA, INPUT_PULLUP);
  pinMode(SCL, INPUT_PULLUP);

  writeReg(0x2A, 0x00);     // Standby mode to change settings
  writeReg(0x0E, 0x10);     // ±2g, high-pass filter enabled
  writeReg(0x2A, 0x01);     // 800 Hz, active mode
}

void loop() {
  Wire.beginTransmission(ADDR);
  Wire.write(0x00);
  Wire.endTransmission(false); // Repeated start
  Wire.requestFrom(ADDR, (uint8_t)7);
  
  uint8_t b[7];
  for (uint8_t i = 0; i < 7; i++) {
    b[i] = Wire.main ? Wire.read() : Wire.read(); // Standard Wire.read()
  }

  // Check if a new Z sample is ready (bit 2 of status register)
  if (b[0] & 0x04) {
    int16_t z = (b[5] << 8) | b[6];
    Serial.println(z >> 4); // Print only the Z value
  }
}