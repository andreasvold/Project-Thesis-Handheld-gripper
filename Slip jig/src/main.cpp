#include <Arduino.h>

const int sliderPin = A0; // Slider potentiometer pin
const int piezoPin  = A1; // Piezoelectric sensor pin (change if using a different pin)

void setup() {
  Serial.begin(250000);
}

void loop() {
  int sliderValue = analogRead(A0);
  int piezoValue  = analogRead(A1);
  
  Serial.print(sliderValue);
  Serial.print(",");
  Serial.println(piezoValue);
}