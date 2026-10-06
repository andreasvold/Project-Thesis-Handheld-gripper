#pragma once
// TaxelReader — measures the oscillation period of a Schmitt NAND multivibrator
// (e.g. one gate of a TC4093BP) using Timer1 input capture on pin D8.
//
// ATmega328P only (Uno / Nano). Timer1 and the capture pin D8 are fixed by the hardware,
// so this is a namespace of functions rather than a class: there is only one capture unit.
//
// Wiring (one gate):
//   Gate input  (pin 1) = sensing plate, plus R (~1 MOhm) to the gate output
//   Gate enable (pin 2) = select pin from the Arduino (or tie to 5V)
//   Gate output (pin 3) = Arduino D8
//
// Keep the oscillation frequency at or below ~50 kHz so the capture interrupt never misses an edge.

#include <Arduino.h>

namespace TaxelReader {

// Configures Timer1 (no prescaler, rising-edge capture, noise canceler). Call once in setup().
//   nDiscard: periods thrown away after enabling (the first one is longer; capacitor starts at Vcc)
//   nPeriods: periods averaged per reading (more = finer resolution, slower reading)
void begin(uint8_t nDiscard = 2, uint16_t nPeriods = 64);

// Enables the oscillator on selPin, measures, disables it again.
// Returns the mean period in timer ticks (1 tick = 1 / F_CPU, 62.5 ns at 16 MHz),
// or -1 if no oscillation was seen within timeoutMs.
float measurePeriod(uint8_t selPin, uint16_t timeoutMs = 50);

// Averages nReadings successful measurements on selPin (keep the sensor untouched).
// Returns the baseline period in ticks, or -1 if every reading failed.
float measureBaseline(uint8_t selPin, uint16_t nReadings = 100);

// Converts a period in ticks to oscillation frequency in kHz.
inline float ticksToKHz(float ticks) { return (F_CPU / 1000.0f) / ticks; }

// Relative period change versus baseline, in parts per million.
// Positive = period got longer = capacitance went up (pressed).
inline float deltaPpm(float periodTicks, float baselineTicks) {
  return (periodTicks / baselineTicks - 1.0f) * 1e6f;
}

}  // namespace TaxelReader