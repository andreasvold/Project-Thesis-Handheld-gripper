#include <Arduino.h>
#include <Arduino_FreeRTOS.h> // Fixed: provides FreeRTOS definitions and vTaskDelay
#include "HX711.h"
#include "loadcell_control.h"

const int LOADCELL_DOUT_PIN = 4; 
const int LOADCELL_SCK_PIN  = 2; 

HX711 scale;

void setupLoadCell() {
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  Serial.println("Reading steady-state baseline...");
  
  scale.tare(100); 
  
  Serial.print("Steady-state offset captured: ");
  Serial.println(scale.get_offset());
  Serial.println("Zero baseline set. Relative change will now be measured.");
}

void vLoadCellTask(void *pvParameters) {
  setupLoadCell();

  for (;;) {
    if (scale.is_ready()) {    
      long relative_value = scale.get_value(1); 
      
      Serial.print("Relative Reading: ");
      Serial.println(relative_value);
    }

    vTaskDelay(pdMS_TO_TICKS(5)); 
  }
}