#include "ChargeAmpSensor.h"

// ATmega328P (Uno): D5 = PD5, D6 = PD6, D7 = PD7
#define RESET_BIT _BV(PD5)
#define CS_BIT    _BV(PD6)
#define CREF_BIT  _BV(PD7)

void ChargeAmpSensor::begin() {
  DDRD |= RESET_BIT | CS_BIT | CREF_BIT; // Pins 5, 6, 7 as outputs
  PORTD &= ~RESET_BIT;                    // Reset switch open (LOW)
  driveState(false);                      // Cs low, Cref high
  setAdcPrescaler(cfg.adcPrescaler);
  delay(100);                             // Let 2.5V reference settle
  _offsetCounts = 0.0f;
}

int32_t ChargeAmpSensor::getStepA() const {
  return stepA;
}

int32_t ChargeAmpSensor::getStepB() const {
  return stepB;
}

int16_t ChargeAmpSensor::a0() const {
  return _a0;
}

int16_t ChargeAmpSensor::a1() const {
  return _a1;
}

int16_t ChargeAmpSensor::b0() const {
  return _b0;
}

int16_t ChargeAmpSensor::b1() const {
  return _b1;
}

void ChargeAmpSensor::driveState(bool csHigh) {
  // One read-modify-write, so both edges happen together.
  uint8_t p = PORTD & ~(CS_BIT | CREF_BIT);
  p |= csHigh ? CS_BIT : CREF_BIT;
  PORTD = p;
}
int32_t ChargeAmpSensor::nullCycle() {
  noInterrupts();
  driveState(false);
  pulseReset();
  int16_t a0 = analogRead(A0);
  delayMicroseconds(cfg.settleUs);   // same wait, but NO edge
  int16_t a1 = analogRead(A0);
  interrupts();
  stepA = (int32_t)a1 - a0;
  return stepA;
}

void ChargeAmpSensor::pulseReset() {
  PORTD |= RESET_BIT;                           // close 4066: shorts feedback C
  delayMicroseconds(cfg.resetUs);
  PORTD &= ~RESET_BIT;                          // open again
  delayMicroseconds(cfg.settleUs);              // let switch charge injection settle
}

 int32_t ChargeAmpSensor::rawCycle() {
  noInterrupts();  // keeps the timing between reset, edge and sample repeatable

  // Step A: D9 rising, D10 falling
  driveState(false);
  pulseReset();
  int16_t rA0 = analogRead(A0);                 // baseline
  driveState(true);                             // edge
  delayMicroseconds(cfg.settleUs);
  int16_t rA1 = analogRead(A0);

  // Step B: D9 falling, D10 rising
  pulseReset(); // since stepB is quite a lot lower than stepA something is probably happening with the reset, settlingtime or something
                // should investigate this.
                // the 4066 switch leaks, which could cause changes between stepA and step. One thing to try is shortening the time window between readings, to see if they become more similar.
                // also the baselines may jitter between the steps. However the size difference is conistent across many readings, so probably not this. 

  int16_t rB0 = analogRead(A0);                 // baseline
  driveState(false);                            // edge
  delayMicroseconds(cfg.settleUs);
  int16_t rB1 = analogRead(A0);

  interrupts();

  // Store raw samples for the getters (outside the interrupt-off window)
  _a0 = rA0;
  _a1 = rA1;
  _b0 = rB0;
  _b1 = rB1;

  stepA = (int32_t)rA1 - rA0;   // negative if Cs > Cref
  stepB = (int32_t)rB1 - rB0;   // positive if Cs > Cref
  return (stepB - stepA);
}

float ChargeAmpSensor::measureCounts(uint16_t averages) {
  if (averages == 0) averages = 1;
  int32_t sum = 0;
  for (uint16_t i = 0; i < averages; i++) {
    sum += rawCycle();
  }
  return (float)sum / (2.0f * (float)averages);  // rawCycle() is 2x the signal
}

float ChargeAmpSensor::readCounts(uint16_t averages) {
  return measureCounts(averages) - _offsetCounts;
}

float ChargeAmpSensor::readVolts(uint16_t averages) {
  return readCounts(averages) * cfg.adcRefVolts / 1023.0f;
}

float ChargeAmpSensor::readDeltaPf(uint16_t averages) {
  // step (V) = Vdrive * (Cs - Cref) / C  ->  (Cs - Cref) = step * C / Vdrive
  return readVolts(averages) * cfg.feedbackCap_pF / cfg.driveVolts;
}

void ChargeAmpSensor::tare(uint16_t averages) {
  _offsetCounts = measureCounts(averages);
}

void ChargeAmpSensor::setAdcPrescaler(uint8_t p) {
  uint8_t bits;
  switch (p) {
    case 16: bits = _BV(ADPS2); break;                           // 1 MHz ADC clock
    case 32: bits = _BV(ADPS2) | _BV(ADPS0); break;              // 500 kHz
    case 64: bits = _BV(ADPS2) | _BV(ADPS1); break;              // 250 kHz
    default: bits = _BV(ADPS2) | _BV(ADPS1) | _BV(ADPS0); break; // 125 kHz (Arduino default)
  }
  ADCSRA = (ADCSRA & ~(_BV(ADPS2) | _BV(ADPS1) | _BV(ADPS0))) | bits;
}