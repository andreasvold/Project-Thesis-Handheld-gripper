#include <Arduino.h>
#include <Arduino_FreeRTOS.h>
#include "stepper_control.h"
#include "loadcell_control.h"

TaskHandle_t stepperTaskHandle = NULL;
TaskHandle_t loadCellTaskHandle = NULL;

void setup() {
  Serial.begin(115200);

  // NOTE: on AVR the stack depth is in BYTES (StackType_t is uint8_t), not words.
  xTaskCreate(vStepperTask,  "Stepper",  192, NULL, 2, &stepperTaskHandle);
  xTaskCreate(vLoadCellTask, "LoadCell", 256, NULL, 1, &loadCellTaskHandle);
}

void loop() {
  // Optional: uncomment to see how much stack each task has left (bytes).
  // Trim or grow the sizes above based on this.
  // Serial.print(F("Stack free  stepper: "));
  // Serial.print(uxTaskGetStackHighWaterMark(stepperTaskHandle));
  // Serial.print(F("  loadcell: "));
  // Serial.println(uxTaskGetStackHighWaterMark(loadCellTaskHandle));
  // delay(2000);
}