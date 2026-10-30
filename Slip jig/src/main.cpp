/*#include <Arduino.h>

const int sliderPin = A0; // Slider potentiometer pin
const int piezoPin  = A1; // Piezoelectric sensor pin (change if using a different pin)

void setup() {
  Serial.begin(250000);
}

void loop() {
  int sliderValue = analogRead(A0);
  int piezoValue  = analogRead(A1);
  
  Serial.print(sliderValue);
  Serial.print(",");
  Serial.println(piezoValue);
}*/

#include <Arduino.h>
#include <Wire.h>

const uint8_t ADDR = 0x1D;     // 0x1C if SA0 is grounded
const int sliderPin = A0;      // Slider potentiometer pin

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void setup() {
  Serial.begin(250000);
  Wire.begin();
  Wire.setClock(400000);    // fast I2C so no samples are missed at 800 Hz

  writeReg(0x2A, 0x00);     // standby, so settings can be changed
  writeReg(0x0E, 0x10);     // ±2 g, high-pass filter on
  writeReg(0x2A, 0x01);     // 800 Hz, active
}

void loop() {
  // Read status + X, Y, Z in one go (registers 0x00 to 0x06)
  Wire.beginTransmission(ADDR);
  Wire.write(0x00);
  Wire.endTransmission(false);    // repeated start (required by chip)
  Wire.requestFrom(ADDR, (uint8_t)7);
  
  uint8_t b[7];
  for (uint8_t i = 0; i < 7; i++) {
    b[i] = Wire.read();
  }

  // Check if a new Z sample is ready
  if (b[0] & 0x04) {              
    int16_t z = (b[5] << 8) | b[6];
    int sliderValue = analogRead(sliderPin);

    // Print both values separated by a comma for the Python script
    Serial.print(sliderValue);
    Serial.print(",");
    Serial.println(z >> 4);       // raw counts, 1024 counts = 1 g
  }
}