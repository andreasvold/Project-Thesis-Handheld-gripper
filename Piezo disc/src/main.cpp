#include <Arduino.h>

// Wiring: D8 -> 220 ohm -> piezo disc -> GND

const uint8_t BUZZ = 8;

const unsigned int FREQ_HZ  = 4000;  // square-wave frequency (try 2000-7000 Hz)
const unsigned long ON_MS   = 100;   // length of each pulse burst
const unsigned long OFF_MS  = 400;   // silence between bursts

const unsigned long HALF_US = 500000UL / FREQ_HZ;   // half period in microseconds

void setup() {
  pinMode(BUZZ, OUTPUT);
  digitalWrite(BUZZ, LOW);
}

void loop() {
  // burst: toggle the pin HIGH/LOW -> digital pulses that make the disc flex
  unsigned long start = millis();
  while (millis() - start < ON_MS) {
    digitalWrite(BUZZ, HIGH);
    delayMicroseconds(HALF_US);
    digitalWrite(BUZZ, LOW);
    delayMicroseconds(HALF_US);
  }

  // pause, pin held LOW
  delay(OFF_MS);
}