#include <Arduino.h>
#include <stdlib.h>        // labs()
#include <util/delay.h>
#include "HX711.h"
#include "MicroSwitch.h"

// STEP must be pin 10 (PB2) for the direct port write in the ISR below.
const uint8_t STEP_PIN        = 10;
const uint8_t DIR_PIN         = 9;
const uint8_t ENA_PIN         = 8;
const uint8_t SWITCH_PIN      = 5;
const uint8_t STOP_SWITCH_PIN = 6;  // Stop switch: moves backward very slowly

const uint8_t LOADCELL_DOUT_PIN = 4;
const uint8_t LOADCELL_SCK_PIN  = 2;

// Stop the jig when the absolute change in load reaches this value.
const long    LOAD_CHANGE_LIMIT = 5000;
const uint8_t TARE_SAMPLES      = 100;    // ~2 s at 10 SPS

// Direction that counts as "backward". If your motor turns the wrong way, swap these.
const uint8_t DIR_BACKWARD = LOW;
const uint8_t DIR_FORWARD  = HIGH;

const uint16_t STEP_RATE_HZ = 50;   // ~3 ms per step (normal speed)

// Timer1 compare values for the two speeds.
// Normal: prescaler 8 -> 2 MHz tick, OCR1A set for STEP_RATE_HZ.
// Slow:   prescaler 1024 -> 15.625 kHz tick.
//         OCR1A = 65535 -> one step every ~4.2 s (slowest the 16-bit timer allows).
//         OCR1A = 15624 -> one step per second (visible, used for testing).
const uint16_t OCR_NORMAL = (uint16_t)(F_CPU / 8UL / STEP_RATE_HZ) - 1;
const uint16_t OCR_SLOW   = 15624;

MicroSwitch button(SWITCH_PIN, true, 50);          // Main toggle switch (Normally Open)
MicroSwitch stopButton(STOP_SWITCH_PIN, true, 50); // Stop switch (Normally Open)
HX711 scale;

// Starts as "forward" so the first press toggles it to backward.
static bool s_forward = true;

// Set from loop(), read in the ISR. A single-byte write is atomic on AVR.
static volatile bool s_running = false;

// Counts every step pulse sent. Incremented in the ISR, read in loop().
static volatile uint32_t s_stepCount = 0;
static uint32_t s_lastPrintedSteps = 0;

// Stores the load cell reading captured right when moving forward begins
static long s_baselineLoad = 0;
static bool s_baselineCaptured = false;

// ---------------- Timer1 step generator ----------------
ISR(TIMER1_COMPA_vect) {
  if (s_running) {
    PORTB |= _BV(PB2);     // STEP high
    _delay_us(3);          // driver needs ~1-3 us minimum pulse width
    PORTB &= ~_BV(PB2);    // STEP low
    s_stepCount++;
  }
}

// Switch the step rate between normal and the slowest possible.
static void setStepTimer(bool slow) {
  noInterrupts();
  if (slow) {
    TCCR1B = _BV(WGM12) | _BV(CS12) | _BV(CS10);  // CTC, prescaler 1024
    OCR1A  = OCR_SLOW;
  } else {
    TCCR1B = _BV(WGM12) | _BV(CS11);              // CTC, prescaler 8
    OCR1A  = OCR_NORMAL;
  }
  TCNT1 = 0;                                      // avoid waiting out an old count
  interrupts();
}

static void setupTimer1() {
  noInterrupts();
  TCCR1A = 0;
  TIMSK1 = _BV(OCIE1A);
  interrupts();
  setStepTimer(false);
}

void setup() {
  Serial.begin(115200);

  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENA_PIN, OUTPUT);
  digitalWrite(ENA_PIN, LOW);            // driver enabled
  digitalWrite(DIR_PIN, DIR_BACKWARD);
  digitalWrite(STEP_PIN, LOW);

  button.begin();
  stopButton.begin();

  // Simple tare: average a few readings with the jig unloaded.
  Serial.println(F("Taring load cell (keep it unloaded)..."));
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  delay(500);
  scale.tare(TARE_SAMPLES);
  Serial.println(F("Tare done."));

  setupTimer1();

  Serial.println(F("Ready. Press switch on D5 to toggle run direction; press switch on D6 to move backward very slowly."));
}

void loop() {
  button.update();
  stopButton.update();

  // Handle main toggle button (normal speed)
  if (button.wasPressed()) {
    s_forward = !s_forward;              // 1st press: backward, 2nd: forward, ...

    s_running = false;                   // pause stepping while DIR changes
    digitalWrite(DIR_PIN, s_forward ? DIR_FORWARD : DIR_BACKWARD);
    delayMicroseconds(20);               // DIR setup time
    setStepTimer(false);                 // back to normal speed
    s_running = true;

    // Reset baseline tracking so a fresh baseline is captured on the next forward run
    s_baselineCaptured = false;

    Serial.println(s_forward ? F("Motor running forward.")
                             : F("Motor running backward."));
  }

  // Handle stop switch on D6: move backward as slowly as possible
  if (stopButton.wasPressed()) {
    s_running = false;                   // pause stepping while DIR changes
    s_forward = false;                   // now moving backward
    digitalWrite(DIR_PIN, DIR_BACKWARD);
    delayMicroseconds(20);               // DIR setup time
    setStepTimer(true);                  // slowest step rate
    s_running = true;

    s_baselineCaptured = false;

    Serial.println(F("Stop switch pressed: moving backward very slowly."));
  }

  // Report each step as it happens, so you can see the motor is being commanded
  uint32_t steps;
  noInterrupts();
  steps = s_stepCount;
  interrupts();
  if (steps != s_lastPrintedSteps) {
    s_lastPrintedSteps = steps;
    Serial.print(F("Step: "));
    Serial.println(steps);
  }

  // Only read when a new sample is ready, so loop() never blocks on the HX711.
  if (scale.is_ready()) {
    long load = scale.get_value(1);      // raw reading minus tare offset
    Serial.println(load);

    // Force limit logic applies while advancing forward
    if (s_running && s_forward) {
      // If we haven't captured a baseline yet for this forward run, grab it now
      if (!s_baselineCaptured) {
        s_baselineLoad = load;
        s_baselineCaptured = true;
        Serial.print(F("Baseline load locked: "));
        Serial.println(s_baselineLoad);
      } else {
        // Check if the absolute difference from the baseline reaches or exceeds 10,000
        long delta = labs(load - s_baselineLoad);
        if (delta >= LOAD_CHANGE_LIMIT) {
          s_running = false;
          Serial.print(F("Load change limit reached! Baseline: "));
          Serial.print(s_baselineLoad);
          Serial.print(F(", Current: "));
          Serial.print(load);
          Serial.print(F(", Delta: "));
          Serial.println(delta);
        }
      }
    }
  }
}