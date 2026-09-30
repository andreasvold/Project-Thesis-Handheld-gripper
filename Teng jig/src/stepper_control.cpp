#include <Arduino.h>
#include <Arduino_FreeRTOS.h>
#include <stdlib.h>      // labs()
#include <limits.h>
#include <util/atomic.h>
#include <util/delay.h>
#include "stepper_control.h"
#include "loadcell_control.h"
#include "MicroSwitch.h"

// STEP must be pin 10 (PB2) for the direct port write in the ISR below.
const uint8_t STEP_PIN = 10;
const uint8_t DIR_PIN  = 9;
const uint8_t ENA_PIN  = 8;
const uint8_t LIMIT_SWITCH_PIN = 5;

const long LOAD_THRESHOLD   = 20000;  // contact
const long UNLOAD_THRESHOLD = 5000;   // considered unloaded
const long RETRACT_STEPS    = 800;

// Was 1500 us high + 1500 us low = 3 ms/step = ~333 steps/s. Same speed here.
const uint16_t STEP_RATE_HZ = 333;

// Safety limit for any single move. SET THIS to a bit more than your real travel.
const long MAX_TRAVEL_STEPS = 30000;

MicroSwitch endstop(LIMIT_SWITCH_PIN, true, 50);

// ---------------- Timer1 step generator ----------------
static volatile long s_stepsLeft = 0;

ISR(TIMER1_COMPA_vect) {
  if (s_stepsLeft > 0) {
    PORTB |= _BV(PB2);     // STEP high
    _delay_us(3);          // driver needs ~1-3 us minimum pulse width
    PORTB &= ~_BV(PB2);    // STEP low
    s_stepsLeft--;
  }
}

static long stepsLeft() {
  long v;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { v = s_stepsLeft; }
  return v;
}

static void stopMotor() {
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { s_stepsLeft = 0; }
}

// Non-blocking: sets direction, then lets the ISR do the stepping.
static void startMove(int dir, long steps) {
  stopMotor();
  digitalWrite(DIR_PIN, (dir > 0) ? HIGH : LOW);
  delayMicroseconds(20);   // DIR setup time
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { s_stepsLeft = steps; }
}

static void setupStepper() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENA_PIN, OUTPUT);
  digitalWrite(ENA_PIN, LOW);   // enabled
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);

  endstop.begin();

  // Timer1, CTC mode, prescaler 8 -> 2 MHz timer clock.
  // Arduino_FreeRTOS uses the watchdog for its tick, so Timer1 is free.
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    TCCR1A = 0;
    TCCR1B = _BV(WGM12) | _BV(CS11);
    OCR1A  = (uint16_t)(F_CPU / 8UL / STEP_RATE_HZ) - 1;
    TCNT1  = 0;
    TIMSK1 = _BV(OCIE1A);
  }
}

static void fault(const __FlashStringHelper *msg) {
  stopMotor();
  digitalWrite(ENA_PIN, HIGH);  // disable driver
  Serial.print(F("[STEPPER] FAULT: "));
  Serial.println(msg);
  for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
}

// ---------------- Task ----------------
void vStepperTask(void *pvParameters) {
  setupStepper();

  // Wait for the load cell instead of guessing with a fixed delay.
  while (!loadcell_ready) vTaskDelay(1);

  // --- 1. CALIBRATION: run toward the switch ---
  Serial.println(F("[STEPPER] Starting calibration..."));
  startMove(-1, MAX_TRAVEL_STEPS);
  while (!endstop.isPressed() && stepsLeft() > 0) {
    endstop.update();
    vTaskDelay(1);
  }
  stopMotor();
  if (!endstop.isPressed()) fault(F("Limit switch not found"));
  Serial.println(F("[SWITCH] Limit switch triggered. Calibration complete."));

  vTaskDelay(pdMS_TO_TICKS(500));

  // --- 2. CONTACT AND RETRACT (5 CYCLES) ---
  Serial.println(F("[STEPPER] Beginning 5 contact & retract cycles..."));

  for (int cycle = 0; cycle < 5; cycle++) {
    Serial.print(F("[STEPPER] Cycle "));
    Serial.print(cycle + 1);
    Serial.println(F(" of 5"));

    // Phase A: make sure the plate is unloaded first
    if (labs(getLoad()) > UNLOAD_THRESHOLD) {
      startMove(-1, MAX_TRAVEL_STEPS);
      while (labs(getLoad()) > UNLOAD_THRESHOLD &&
             !endstop.isPressed() && stepsLeft() > 0) {
        endstop.update();
        vTaskDelay(1);
      }
      stopMotor();
    }

    // Phase B: advance until contact
    Serial.println(F("[STEPPER] Advancing to hit load cell..."));
    startMove(1, MAX_TRAVEL_STEPS);
    while (labs(getLoad()) <= LOAD_THRESHOLD && stepsLeft() > 0) {
      endstop.update();
      vTaskDelay(1);
    }
    stopMotor();
    if (labs(getLoad()) <= LOAD_THRESHOLD) fault(F("No contact within max travel"));

    Serial.print(F("[LOADCELL] Contact made! Reading: "));
    Serial.println(getLoad());

    // Phase C: retract a fixed number of steps (ISR counts them)
    Serial.println(F("[STEPPER] Retracting..."));
    startMove(-1, RETRACT_STEPS);
    while (stepsLeft() > 0 && !endstop.isPressed()) {
      endstop.update();
      vTaskDelay(1);
    }
    stopMotor();

    vTaskDelay(pdMS_TO_TICKS(500));
  }

  Serial.println(F("[STEPPER] All 5 cycles complete. Task idling."));
  for (;;) vTaskDelay(pdMS_TO_TICKS(1000));
}