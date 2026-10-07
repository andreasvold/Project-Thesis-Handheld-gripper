#include "ChargeAmpSensor.h"

// ATmega328P (Uno): D8 = PB0, D9 = PB1, D10 = PB2
#define RESET_BIT _BV(PB0)
#define CS_BIT    _BV(PB1)
#define CREF_BIT  _BV(PB2)

void ChargeAmpSensor::begin() {
  DDRB |= RESET_BIT | CS_BIT | CREF_BIT;       // D8, D9, D10 as outputs
  PORTB &= ~RESET_BIT;                          // switch open
  driveState(false);                            // Cs low, Cref high
  setAdcPrescaler(cfg.adcPrescaler);
  delay(100);                                   // let the 2.5 V reference settle (tau ~5 ms)
  _offsetCounts = 0.0f;
}

void ChargeAmpSensor::driveState(bool csHigh) {
  // One read-modify-write, so both edges happen together.
  uint8_t p = PORTB & ~(CS_BIT | CREF_BIT);
  p |= csHigh ? CS_BIT : CREF_BIT;
  PORTB = p;
}

void ChargeAmpSensor::pulseReset() {
  PORTB |= RESET_BIT;                           // close 4066: shorts feedback C
  delayMicroseconds(cfg.resetUs);
  PORTB &= ~RESET_BIT;                          // open again
  delayMicroseconds(cfg.settleUs);              // let switch charge injection settle
}

int32_t ChargeAmpSensor::rawCycle() {
  noInterrupts();  // keeps the timing between reset, edge and sample repeatable

  // Step A: D9 rising, D10 falling
  driveState(false);
  pulseReset();
  int16_t a0 = analogRead(A0);                  // baseline
  driveState(true);                             // edge
  delayMicroseconds(cfg.settleUs);
  int16_t a1 = analogRead(A0);

  // Step B: D9 falling, D10 rising
  pulseReset();
  int16_t b0 = analogRead(A0);                  // baseline
  driveState(false);                            // edge
  delayMicroseconds(cfg.settleUs);
  int16_t b1 = analogRead(A0);

  interrupts();

  int32_t stepA = (int32_t)a1 - a0;             // negative if Cs > Cref
  int32_t stepB = (int32_t)b1 - b0;             // positive if Cs > Cref
  return stepB - stepA;
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