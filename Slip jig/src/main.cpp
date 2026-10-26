#include <Arduino.h>

const uint8_t STEP_PIN = 10;
const uint8_t DIR_PIN  = 9;
const uint8_t ENA_PIN  = 8;

// Standard 1.8° motor is 200 steps/rev. 
// IMPORTANT (DM542): If your DM542 DIP switches are set to microstepping 
// (e.g., 1600 steps/rev), update this number to match your driver setting!
const int STEPS_PER_REVOLUTION = 200; 
const int TARGET_REVOLUTIONS = 5;

void setup() {
    // Configure pins as outputs
    pinMode(STEP_PIN, OUTPUT);
    pinMode(DIR_PIN, OUTPUT);
    pinMode(ENA_PIN, OUTPUT);

    // Enable the driver (LOW enables the DM542)
    digitalWrite(ENA_PIN, LOW);
}

void loop() {
    // 1. Rotate in one direction for 5 full revolutions
    digitalWrite(DIR_PIN, HIGH);
    for (long i = 0; i < (long)STEPS_PER_REVOLUTION * TARGET_REVOLUTIONS; i++) {
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(1000); // Controls speed (lower = faster)
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(1000);
    }

    // Pause for 1 second
    delay(1000);

    // 2. Rotate in the reverse direction for 5 full revolutions
    digitalWrite(DIR_PIN, LOW);
    for (long i = 0; i < (long)STEPS_PER_REVOLUTION * TARGET_REVOLUTIONS; i++) {
        digitalWrite(STEP_PIN, HIGH);
        delayMicroseconds(1000);
        digitalWrite(STEP_PIN, LOW);
        delayMicroseconds(1000);
    }

    // Pause for 1 second
    delay(1000);
}