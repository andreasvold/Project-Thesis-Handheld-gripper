#include <Arduino.h>
#include "ChargeAmpSensor.h"

ChargeAmpSensor sensor;
const uint8_t N = 100;
int16_t buf[N][4];

void setup() {
  Serial.begin(115200);

  sensor.cfg.feedbackCap_pF = 1;   // set to your actual C
  sensor.cfg.adcPrescaler   = 32;     // 32 is a good speed/accuracy compromise
  sensor.begin();

  Serial.println(F("Taring: keep the sensor unloaded..."));
  sensor.tare(256);
  Serial.println(F("counts,volts,deltaC_pF"));
}

void loop() {
  const uint16_t N = 8; // Reduced from 64 to speed up reading rate
  float counts = sensor.readCounts(N);
  float volts  = sensor.readVolts(N);
  float dPf    = sensor.readDeltaPf(N);

  int32_t netResult = sensor.rawCycle();

  // Print as comma-separated values for plot:
  Serial.print(netResult);
  Serial.print(",");
  Serial.print(sensor.getStepA());
  Serial.print(",");
  Serial.println(sensor.getStepB());

  /*
  int32_t net = sensor.rawCycle();

  Serial.print(sensor.a0()); Serial.print(',');
  Serial.print(sensor.a1()); Serial.print(',');
  Serial.print(sensor.b0()); Serial.print(',');
  Serial.println(sensor.b1());*/
  
  //Serial.print(counts, 2);
  //Serial.print(',');
  //Serial.print(volts, 4);
  //Serial.print(',');
  //Serial.println(dPf, 4);
}
/*void loop() {
  Serial.flush();            // make sure the UART is idle
  delay(20);

  for (uint8_t i = 0; i < N; i++) {      // no serial activity in here
    sensor.rawCycle();
    buf[i][0] = sensor.a0();  buf[i][1] = sensor.a1();
    buf[i][2] = sensor.b0();  buf[i][3] = sensor.b1();
  }

  for (uint8_t i = 0; i < N; i++) {
    Serial.print(buf[i][0]); Serial.print(',');
    Serial.print(buf[i][1]); Serial.print(',');
    Serial.print(buf[i][2]); Serial.print(',');
    Serial.println(buf[i][3]);
  }
  delay(2000);
}*/

/*
// Bench test for the 4066 reset switch + charge amp.  Open the serial monitor at 115200
// and send a single character (no line ending needed) to run a test.
#include <Arduino.h>

#define PIN_RESET 5   // 4066 pin 13 (CTRL A) -> Uno D5, same pin the ChargeAmpSensor driver uses
#define PIN_CS    6   // Cs drive
#define PIN_CREF  7   // Cref drive
#define PIN_ADC   A0  // op-amp output
#define VREF      5.0f

static inline void resetClose() { digitalWrite(PIN_RESET, HIGH); }
static inline void resetOpen()  { digitalWrite(PIN_RESET, LOW);  }
static inline void drive(bool csHigh) {
  digitalWrite(PIN_CS,   csHigh);
  digitalWrite(PIN_CREF, !csHigh);
}
static inline void resetPulse(uint16_t closedUs = 20, uint16_t settleUs = 20) {
  resetClose(); delayMicroseconds(closedUs);
  resetOpen();  delayMicroseconds(settleUs);
}
static float avgRead(uint16_t n) {
  uint32_t s = 0;
  for (uint16_t i = 0; i < n; i++) s += analogRead(PIN_ADC);
  return (float)s / n;
}
static void printCounts(const char* label, float c) {
  Serial.print(label); Serial.print(c, 1);
  Serial.print(" counts = "); Serial.print(c * VREF / 1023.0f, 3); Serial.println(" V");
}

void menu() {
  Serial.println(F("\n=== 4066 / charge amp bench test ==="));
  Serial.println(F("1  Pin check: slow-toggle each pin (use a DC multimeter)"));
  Serial.println(F("2  Follower test: reset held closed, A0 should equal the + input"));
  Serial.println(F("3  Open-switch drift: does the output hold after reset opens?"));
  Serial.println(F("4  Step vs delay: does the edge response decay (leak)?"));
  Serial.println(F("5  Reset recovery: does a reset really bring the output back?"));
}

// 1: lets a multimeter confirm every control/drive pin reaches the right place
void testPins() {
  struct P { uint8_t pin; const char* name; } pins[] = {
    {PIN_RESET, "RESET (D5 -> 4066 pin 13)"},
    {PIN_CS,    "CS drive (D6)"},
    {PIN_CREF,  "CREF drive (D7)"}};
  Serial.println(F("Each pin goes HIGH 4 s then LOW 4 s. Measure DC at the far end of the wire."));
  for (auto& p : pins) {
    Serial.print(p.name); Serial.println(F("  HIGH (expect ~4.9 V)"));
    digitalWrite(p.pin, HIGH); delay(4000);
    Serial.print(p.name); Serial.println(F("  LOW  (expect 0 V)"));
    digitalWrite(p.pin, LOW);  delay(4000);
  }
  Serial.println(F("Done. If RESET never shows 4.9 V at 4066 pin 13, the reset is not wired to the right pin."));
}

// 2: switch closed => op-amp is a unity follower => A0 = + input voltage, independent of drive
void testFollower() {
  resetClose(); delay(5);
  drive(false); delay(5); float a = avgRead(200);
  drive(true);  delay(5); float b = avgRead(200);
  drive(false);
  Serial.println(F("Reset CLOSED (follower). Compare with your multimeter on the + input."));
  printCounts("Cref high: ", a);
  printCounts("Cs high:   ", b);
  Serial.print(F("Difference: ")); Serial.print(b - a, 1); Serial.println(F(" counts"));
  Serial.println(F("PASS: both match the + input, difference ~0 (+-1)."));
  Serial.println(F("FAIL: differs from + input -> switch not closing / wrong pin / op-amp problem."));
  Serial.println(F("FAIL: difference != 0 -> drive couples through, or switch only partly on."));
  resetOpen();
}

// 3: after reset opens with no edges, a good switch holds the level (leakage only)
void testDrift() {
  const uint8_t N = 12;
  const uint16_t spacingUs = 500;
  const uint8_t trials = 32;
  float sum[N] = {0};
  drive(false);
  for (uint8_t t = 0; t < trials; t++) {
    resetPulse(20, 20);
    for (uint8_t i = 0; i < N; i++) {
      sum[i] += analogRead(PIN_ADC);
      delayMicroseconds(spacingUs);
    }
    delay(2);
  }
  Serial.println(F("Output vs time after reset opens (no drive edge), avg of 32 trials:"));
  for (uint8_t i = 0; i < N; i++) {
    Serial.print(F("t~")); Serial.print((uint32_t)i * (spacingUs + 20)); Serial.print(F(" us: "));
    Serial.println(sum[i] / trials, 2);
  }
  Serial.println(F("PASS: flat within ~1-2 counts over 6 ms."));
  Serial.println(F("FAIL: ramps or decays steadily -> leakage across Cf (board, floating control pin)."));
}

// 4: ideal charge amp gives the same step no matter how long you wait. A leak decays it.
void testStepVsDelay() {
  const uint16_t delays[] = {0, 2, 5, 10, 20, 50, 100, 200, 500, 1000};
  const uint8_t trials = 64;
  Serial.println(F("delay_us   stepA(Cs rises)   stepB(Cs falls)"));
  for (uint16_t d : delays) {
    float sA = 0, sB = 0;
    for (uint8_t t = 0; t < trials; t++) {
      drive(false); resetPulse(20, 20);
      float a0 = analogRead(PIN_ADC);
      drive(true);  delayMicroseconds(d);
      float a1 = analogRead(PIN_ADC);
      resetPulse(20, 20);
      float b0 = analogRead(PIN_ADC);
      drive(false); delayMicroseconds(d);
      float b1 = analogRead(PIN_ADC);
      sA += a1 - a0; sB += b1 - b0;
    }
    Serial.print(d); Serial.print(F("\t\t"));
    Serial.print(sA / trials, 1); Serial.print(F("\t\t"));
    Serial.println(sB / trials, 1);
  }
  Serial.println(F("PASS: steps are constant versus delay, stepA ~ -stepB."));
  Serial.println(F("FAIL: steps shrink as delay grows -> charge leaks off Cf (time constant visible here)."));
  Serial.println(F("FAIL: both steps tiny at every delay -> leak is faster than ~5 us, or drive not reaching Cs/Cref."));
}

// 5: displace the output with an edge, then reset: it must return to baseline
void testResetRecovery() {
  const uint8_t trials = 64;
  float base = 0, disp = 0, after = 0;
  for (uint8_t t = 0; t < trials; t++) {
    drive(false); resetPulse(20, 20);
    base += analogRead(PIN_ADC);
    drive(true);  delayMicroseconds(20);
    disp += analogRead(PIN_ADC);
    resetPulse(20, 20);                 // reset while drive is still high
    after += analogRead(PIN_ADC);
    drive(false);
  }
  printCounts("baseline:       ", base / trials);
  printCounts("after edge:     ", disp / trials);
  printCounts("after reset:    ", after / trials);
  Serial.println(F("PASS: 'after reset' ~ baseline (within a few counts, charge injection aside)."));
  Serial.println(F("FAIL: 'after reset' stays near 'after edge' -> reset isn't closing the switch."));
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_RESET, OUTPUT); pinMode(PIN_CS, OUTPUT); pinMode(PIN_CREF, OUTPUT);
  resetOpen(); drive(false);
  ADCSRA = (ADCSRA & ~0x07) | 0x04;      // ADC prescaler 16 (1 MHz ADC clock)
  analogRead(PIN_ADC);                   // discard first conversion
  delay(200);
  menu();
}

void loop() {
  if (!Serial.available()) return;
  char c = Serial.read();
  switch (c) {
    case '1': testPins();          break;
    case '2': testFollower();      break;
    case '3': testDrift();         break;
    case '4': testStepVsDelay();   break;
    case '5': testResetRecovery(); break;
    default: return;
  }
  menu();
}
*/