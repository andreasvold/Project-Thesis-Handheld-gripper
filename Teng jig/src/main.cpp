#include <Arduino.h>
#include "stepper_control.h"
#include "loadcell_control.h"

void setup() {
  Serial.begin(9600);
  
  // Call initialization routines from separate files
  setupStepper();
  setupLoadCell();
}

void loop() {
  // Call operational routines sequentially
  runLoadCell();
  runStepper();
  
  // Adjusted timing delay so the loop runs fluidly
  delay(50); 
}
