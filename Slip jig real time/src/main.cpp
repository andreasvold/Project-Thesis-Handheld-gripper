#include <Arduino.h>
#include <Wire.h>

// =====================================================================
//  FEATURE SELECTION  (true = enabled, false = disabled)
// =====================================================================
constexpr bool ENABLE_ACCEL = false;
constexpr bool ENABLE_PIEZO = true;

// Serial baud rate. Must match BAUD_RATE in the Python script and
// monitor_speed in platformio.ini. Ignored if using native USB CDC.
constexpr uint32_t SERIAL_BAUD = 115200;

// Output rate when the accelerometer is disabled (piezo-only mode).
// With the accelerometer enabled, lines are sent at its data-ready rate.
constexpr uint32_t PIEZO_ONLY_RATE_HZ = 1;

// =====================================================================
//  PINS (ESP32-C6)
// =====================================================================
constexpr uint8_t PIN_SDA   = 4;
constexpr uint8_t PIN_SCL   = 5;
constexpr uint8_t PIEZO_PIN = 1;      // ADC channel, GPIO0-6 only on C6

// =====================================================================
//  MMA8452Q
// =====================================================================
constexpr uint8_t ADDR             = 0x1D;  // 0x1C if SA0 is grounded
constexpr uint8_t REG_STATUS       = 0x00;
constexpr uint8_t REG_WHO_AM_I     = 0x0D;
constexpr uint8_t REG_XYZ_DATA_CFG = 0x0E;
constexpr uint8_t REG_CTRL1        = 0x2A;

constexpr int ADC_MAX_COUNTS = 4095;     // ESP32 ADC is 12-bit

// 12-bit (MMA8452Q) -> shift 4, 14-bit (MMA8451Q) -> shift 2
uint8_t dataShift = 4;

// =====================================================================
//  Piezo state (min/max window between output lines)
// =====================================================================
int piezoLast = 0;
int piezoMin  = ADC_MAX_COUNTS;
int piezoMax  = 0;

constexpr uint32_t OUTPUT_PERIOD_US = 1000000UL / PIEZO_ONLY_RATE_HZ;
uint32_t nextOutputUs = 0;

// =====================================================================
//  I2C helpers
// =====================================================================
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

// =====================================================================
//  Accelerometer
// =====================================================================
void initAccel() {
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);

  uint8_t id = readReg(REG_WHO_AM_I);
  if (id == 0x1A) dataShift = 2;         // MMA8451Q
  else if (id != 0x2A) {                 // MMA8452Q = 0x2A
    Serial.print(F("Unexpected WHO_AM_I: 0x"));
    Serial.println(id, HEX);
  }

  writeReg(REG_CTRL1, 0x00);             // Standby to change settings
  writeReg(REG_XYZ_DATA_CFG, 0x10);      // +/-2g, high-pass filter on output
  writeReg(REG_CTRL1, 0x01);             // 800 Hz, active
}

// Returns true and fills x/y/z only when a new sample is ready.
bool readAccel(int16_t &x, int16_t &y, int16_t &z) {
  Wire.beginTransmission(ADDR);
  Wire.write(REG_STATUS);
  Wire.endTransmission(false);
  if (Wire.requestFrom(ADDR, (uint8_t)7) != 7) return false;

  uint8_t b[7];
  for (uint8_t i = 0; i < 7; i++) b[i] = Wire.read();

  if (!(b[0] & 0x08)) return false;      // ZYXDR: new X, Y and Z ready

  x = (int16_t)((b[1] << 8) | b[2]) >> dataShift;
  y = (int16_t)((b[3] << 8) | b[4]) >> dataShift;
  z = (int16_t)((b[5] << 8) | b[6]) >> dataShift;
  return true;
}

// =====================================================================
//  Piezo
// =====================================================================
void samplePiezo() {
  int v = analogRead(PIEZO_PIN);
  piezoLast = v;
  if (v < piezoMin) piezoMin = v;
  if (v > piezoMax) piezoMax = v;
}

// =====================================================================
//  Output: always the same CSV line, disabled channels print 0
// =====================================================================
void emitRow(uint32_t t, int16_t x, int16_t y, int16_t z) {
  int piezo = 0;
  int pp    = 0;

  if (ENABLE_PIEZO) {
    piezo = piezoLast;
    pp    = piezoMax - piezoMin;
    piezoMin = ADC_MAX_COUNTS;
    piezoMax = 0;
  }

  Serial.print(t);     Serial.print(',');
  Serial.print(x);     Serial.print(',');
  Serial.print(y);     Serial.print(',');
  Serial.print(z);     Serial.print(',');
  Serial.print(piezo); Serial.print(',');
  Serial.println(pp);
}

// =====================================================================
//  Arduino entry points
// =====================================================================
void setup() {
  Serial.begin(SERIAL_BAUD);

  if (ENABLE_PIEZO) analogReadResolution(12);
  if (ENABLE_ACCEL) initAccel();

  Serial.println(F("t_us,ax,ay,az,piezo,piezo_pp"));
  nextOutputUs = micros();
}

void loop() {
  if (ENABLE_PIEZO) samplePiezo();       // sample as fast as possible

  if (ENABLE_ACCEL) {
    int16_t x, y, z;
    if (!readAccel(x, y, z)) return;     // no new sample yet
    emitRow(micros(), x, y, z);
  } else {
    // Piezo-only: emit at a fixed rate. The wrap-safe comparison
    // handles micros() rollover.
    uint32_t now = micros();
    if ((int32_t)(now - nextOutputUs) >= 0) {
      nextOutputUs += OUTPUT_PERIOD_US;
      emitRow(now, 0, 0, 0);
    }
  }
}