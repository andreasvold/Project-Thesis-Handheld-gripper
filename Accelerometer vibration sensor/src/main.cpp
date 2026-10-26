// Single-taxel capacitive reader — one Schmitt NAND gate (TC4093BP) + Arduino Uno/Nano.
// Based on Ulmen & Cutkosky's multivibrator skin: measure oscillation PERIOD, not voltage.
//
// Wiring (gate A only):
//   Pin 1  = sensing plate, plus 1 MOhm to pin 3
//   Pin 2  = SELECT from D7
//   Pin 3  = output -> Arduino D8
//   Pin 14 -> 5V, pin 7 -> GND, 100 nF between pins 14 and 7
//   Unused inputs 5, 6, 8, 9, 12, 13 -> GND; outputs 4, 10, 11 left open
//
// Output (9600 baud, tab-separated): period_ticks, freq_kHz, delta_ppm

#include <Arduino.h>
#include "TaxelReader.h"

constexpr uint8_t  SEL_SENSOR = 7;
constexpr uint8_t  N_DISCARD  = 2;    // first periods after enabling are longer -> discard
constexpr uint16_t N_PERIODS  = 64;   // periods averaged per reading
constexpr uint16_t N_BASELINE = 100;  // startup readings for the no-touch baseline (don't touch!)

float baseline = -1.0f;

void setup() {
  Serial.begin(9600);
  pinMode(SEL_SENSOR, OUTPUT);
  digitalWrite(SEL_SENSOR, LOW);

  TaxelReader::begin(N_DISCARD, N_PERIODS);

  delay(200);
  baseline = TaxelReader::measureBaseline(SEL_SENSOR, N_BASELINE);
  if (baseline < 0) {
    Serial.println(F("No oscillation during baseline; check wiring. Using first good reading instead."));
  }

  Serial.println(F("period_ticks\tfreq_kHz\tdelta_ppm"));
}

void loop() {
  float p = TaxelReader::measurePeriod(SEL_SENSOR);
  if (p < 0) {
    Serial.println(F("No oscillation detected."));
    delay(500);
    return;
  }
  if (baseline < 0) baseline = p;  // recover if the startup baseline failed

  // Serial.print(p, 2);
  Serial.print('\t');
  Serial.print(TaxelReader::ticksToKHz(p), 2);
  Serial.print('\t');
  Serial.println(TaxelReader::deltaPpm(p, baseline), 0);

  delay(10);
}