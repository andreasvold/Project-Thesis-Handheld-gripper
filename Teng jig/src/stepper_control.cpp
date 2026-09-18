#include <Arduino.h>
#include <Arduino_FreeRTOS.h> // Fixed: provides FreeRTOS definitions and pdMS_TO_TICKS
#include "stepper_control.h"

const int STEP_PIN = 10; 
const int DIR_PIN  = 8;  
const int ENA_PIN  = 7;  

const int STEPS_PER_DIRECTION = 200; 
const int STEP_DELAY_US       = 2000; 

void setupStepper() {
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENA_PIN, OUTPUT);

  digitalWrite(ENA_PIN, LOW);
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);
}

void vStepperTask(void *pvParameters) {
  setupStepper();

  for (;;) {
    // --- Move Forward ---
    digitalWrite(DIR_PIN, HIGH);
    for (int i = 0; i < STEPS_PER_DIRECTION; i++) {
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(STEP_DELAY_US);
      digitalWrite(STEP_PIN, LOW);
      delayMicroseconds(STEP_DELAY_US);
    }
    vTaskDelay(pdMS_TO_TICKS(500));

    // --- Move Backward ---
    digitalWrite(DIR_PIN, LOW);
    for (int i = 0; i < STEPS_PER_DIRECTION; i++) {
      digitalWrite(STEP_PIN, HIGH);
      delayMicroseconds(STEP_DELAY_US);
      digitalWrite(STEP_PIN, LOW);
      delayMicroseconds(STEP_DELAY_US);
    }
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}