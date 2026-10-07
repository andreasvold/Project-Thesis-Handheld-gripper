#pragma once
#include <Arduino.h>

// Driver for the charge-amplifier capacitive sensor circuit (Arduino Uno / ATmega328P).
//
// Pins are FIXED because the driver writes PORTB directly, so that the Cs and Cref
// edges happen at exactly the same instant:
//
//   D8  (PB0) -> 4066 control pin 13   (reset switch across feedback capacitor C)
//   D9  (PB1) -> Cs   drive
//   D10 (PB2) -> Cref drive (always the opposite level of D9)
//   A0        <- op-amp output
//
// One measurement cycle (see rawCycle()):
//   A) reset, read baseline, D9 rises / D10 falls, read  -> stepA (negative if Cs > Cref)
//   B) reset, read baseline, D9 falls / D10 rises, read  -> stepB (positive if Cs > Cref)
//   result = stepB - stepA  (= 2x the signal, in ADC counts)
// Using both polarities cancels leakage drift and any switch charge-injection offset.

struct ChargeAmpConfig {
  float   feedbackCap_pF = 4.7f;  // the feedback capacitor C in your circuit
  float   driveVolts     = 5.0f;  // logic-high level of D9/D10 (Uno on 5 V)
  float   adcRefVolts    = 5.0f;  // ADC reference (default AVcc)
  uint8_t resetUs        = 5;     // how long the 4066 stays closed
  uint8_t settleUs       = 10;    // wait after reset and after each edge, before sampling
  uint8_t adcPrescaler   = 32;    // 16, 32, 64 or 128 (128 = Arduino default, slowest)
};

class ChargeAmpSensor {
 public:
  ChargeAmpConfig cfg;  // edit fields before calling begin()

  // Sets up pins and ADC speed, then waits for the Vmid reference to settle.
  void begin();

  // One full A+B cycle. Returns stepB - stepA in ADC counts (2x signal).
  int32_t rawCycle();

  // Average over N cycles. Return value is the signal in ADC counts, tare removed.
  float readCounts(uint16_t averages = 64);

  // Same signal in volts at the op-amp output: Vdrive * (Cs - Cref) / C.
  float readVolts(uint16_t averages = 64);

  // Estimated change in (Cs - Cref) in pF relative to the tare point.
  float readDeltaPf(uint16_t averages = 64);

  // Store the current reading as zero. Call with no force applied.
  void tare(uint16_t averages = 256);

 private:
  float _offsetCounts = 0.0f;

  float measureCounts(uint16_t averages);  // average without tare
  void  driveState(bool csHigh);           // sets D9 and D10 in one port write
  void  pulseReset();
  void  setAdcPrescaler(uint8_t p);
};