#include <Arduino.h>
#include "HX711.h"
#include "loadcell_control.h"

const int LOADCELL_DOUT_PIN = 4; 
const int LOADCELL_SCK_PIN  = 2; 

HX711 scale;

void setupLoadCell() {
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  Serial.println("Reading steady-state baseline...");
  
  // Built-in method: averages 100 raw samples and sets it as the zero offset
  scale.tare(100); 
  
  Serial.print("Steady-state offset captured: ");
  Serial.println(scale.get_offset()); // Built-in method to view saved offset
  Serial.println("Zero baseline set. Relative change will now be measured.");
}

void runLoadCell() {
  // Only execute when the HX711 chip has finished its physical ADC conversion
  if (scale.is_ready()) {    
    // Built-in method: returns (Raw Reading - Offset) automatically
    long relative_value = scale.get_value(1); 
    
    Serial.print("Relative Reading: ");
    Serial.println(relative_value);
  }
}