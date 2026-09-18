#include <Arduino.h>
#include <Arduino_FreeRTOS.h> // Fixed: provides xTaskCreate, TaskHandle_t, vTaskDelete
#include "stepper_control.h"
#include "loadcell_control.h"

TaskHandle_t stepperTaskHandle = NULL;
TaskHandle_t loadCellTaskHandle = NULL;

void setup() {
  Serial.begin(115200);

  xTaskCreate(
    vStepperTask,
    "StepperTask",
    128,            // Note: On AVR/Uno, stack is in words (128 words = 256 bytes)
    NULL,
    2,
    &stepperTaskHandle
  );

  xTaskCreate(
    vLoadCellTask,
    "LoadCellTask",
    128,            // Keep stack allocations small on Uno (2KB SRAM total)
    NULL,
    1,
    &loadCellTaskHandle
  );
}

void loop() {
  // Empty loop: FreeRTOS scheduler manages execution automatically on AVR
}