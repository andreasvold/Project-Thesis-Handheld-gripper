#include <Arduino.h>

void setup() {
  // Initialize serial communication at a fast baud rate
  Serial.begin(115200);
}

void loop() {
  // Read analog pin A0
  int sensorValue = analogRead(A1);
  
  // Print the value to the serial monitor
  Serial.println(sensorValue);
  
  // Optional: Adjust delay to control sampling rate (e.g., ~100Hz)
  delay(0.01); 
}