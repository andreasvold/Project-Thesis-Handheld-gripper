#include "CapSensor.h"

// Timer1 drives D9 (OC1A) with prescaler 8, toggling the pin on each
// compare match: f = F_CPU / (2 * 8 * (OCR1A + 1)).
static const uint8_t  EXCITE_PIN = 9;
static const uint16_t PRESCALER  = 8;

CapSensor::CapSensor(const CapSensorConfig& cfg)
  : cfg_(cfg), ocr_(0), running_(false) {
  uint32_t hz = cfg_.exciteHz;
  if (hz < 16)    hz = 16;      // OCR1A tops out at 65535
  if (hz > 50000) hz = 50000;
  uint32_t ocr = F_CPU / (2UL * PRESCALER * hz);
  if (ocr > 0) ocr -= 1;
  if (ocr > 65535) ocr = 65535;
  ocr_ = (uint16_t)ocr;
}

void CapSensor::begin() {
  pinMode(EXCITE_PIN, OUTPUT);
  digitalWrite(EXCITE_PIN, LOW);
  analogRead(cfg_.sensePin);    // first conversion after power-up is often off
  startExcitation();
}

void CapSensor::startExcitation() {
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  TCNT1  = 0;
  OCR1A  = ocr_;
  TCCR1A = _BV(COM1A0);                 // toggle OC1A (D9) on compare match
  TCCR1B = _BV(WGM12) | _BV(CS11);      // CTC mode, prescaler 8
  interrupts();
  running_ = true;
}

void CapSensor::stopExcitation() {
  noInterrupts();
  TCCR1A = 0;
  TCCR1B = 0;
  interrupts();
  digitalWrite(EXCITE_PIN, LOW);
  running_ = false;
}

float CapSensor::exciteHz() const {
  return (float)F_CPU / (2.0f * PRESCALER * ((uint32_t)ocr_ + 1));
}

int CapSensor::read() {
  return analogRead(cfg_.sensePin);
}

float CapSensor::capture(uint16_t* samples, uint8_t* levels, uint16_t n) {
  if (n == 0) return 0.0f;

  unsigned long t0 = micros();
  for (uint16_t i = 0; i < n; i++) {
    if (levels) levels[i] = (PINB & _BV(PB1)) ? 1 : 0;   // D9 = PB1 on the Uno
    samples[i] = analogRead(cfg_.sensePin);
  }
  unsigned long elapsed = micros() - t0;

  return (float)elapsed / n;
}