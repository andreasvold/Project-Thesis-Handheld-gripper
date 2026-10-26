#include "TaxelReader.h"

namespace {

uint8_t  gDiscard = 2;
uint16_t gPeriods = 64;

volatile uint16_t gLastCap;
volatile uint32_t gSumTicks;
volatile uint16_t gEdges;
volatile bool     gDone;

}  // namespace

// Timer1 input capture: ICR1 holds the hardware-latched timestamp of each rising edge on D8.
ISR(TIMER1_CAPT_vect) {
  uint16_t now = ICR1;
  if (gEdges > gDiscard) gSumTicks += (uint16_t)(now - gLastCap);  // unsigned math handles wraparound
  gLastCap = now;
  gEdges++;
  if (gEdges > gDiscard + gPeriods) {
    TIMSK1 &= ~_BV(ICIE1);  // stop capturing
    gDone = true;
  }
}

namespace TaxelReader {

void begin(uint8_t nDiscard, uint16_t nPeriods) {
  gDiscard = nDiscard;
  gPeriods = nPeriods;

  pinMode(8, INPUT);  // ICP1

  // Timer1: normal mode, no prescaler, rising-edge capture, input noise canceler on
  TCCR1A = 0;
  TCCR1B = _BV(ICNC1) | _BV(ICES1) | _BV(CS10);
  TIMSK1 = 0;
}

float measurePeriod(uint8_t selPin, uint16_t timeoutMs) {
  digitalWrite(selPin, HIGH);  // start oscillating

  noInterrupts();
  gEdges = 0;
  gSumTicks = 0;
  gDone = false;
  TIFR1 = _BV(ICF1);     // clear any stale capture flag
  TIMSK1 |= _BV(ICIE1);  // enable capture interrupt
  interrupts();

  uint32_t t0 = millis();
  while (!gDone) {
    if (millis() - t0 > timeoutMs) {  // no oscillation: check wiring, R, supply
      TIMSK1 &= ~_BV(ICIE1);
      digitalWrite(selPin, LOW);
      return -1.0f;
    }
  }

  digitalWrite(selPin, LOW);  // stop oscillating

  noInterrupts();
  uint32_t sum = gSumTicks;
  interrupts();
  return (float)sum / gPeriods;
}

float measureBaseline(uint8_t selPin, uint16_t nReadings) {
  float sum = 0;
  uint16_t n = 0;
  for (uint16_t i = 0; i < nReadings; i++) {
    float p = measurePeriod(selPin);
    if (p > 0) {
      sum += p;
      n++;
    }
  }
  return (n > 0) ? sum / n : -1.0f;
}

}  // namespace TaxelReader