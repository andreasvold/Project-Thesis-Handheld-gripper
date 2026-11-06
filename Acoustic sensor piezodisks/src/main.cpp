#include <Arduino.h>

const int TRANSMIT_PIN = 8;
const int RECEIVE_PIN = A0;

// --- Frequency Control ---
const unsigned int TARGET_FREQ_HZ =4000; // Continuous frequency (try 2000 - 7000 Hz)

void setup() {
  Serial.begin(115200);
  pinMode(RECEIVE_PIN, INPUT);
  
  // Start continuous background square wave generation on pin 8
  tone(TRANSMIT_PIN, TARGET_FREQ_HZ);
  
  Serial.print("Continuous Piezo Sensor Running at ");
  Serial.print(TARGET_FREQ_HZ);
  Serial.println(" Hz");
}

void loop() {
  // Continuously read the live voltage from the receiving piezodisk
  int val = analogRead(RECEIVE_PIN);

  // Print the raw reading immediately (ideal for your Python plotter or Serial Plotter)
  Serial.println(val);

  // Optional: small delay if you want to throttle the print speed (e.g., every 5ms)
  // Remove or lower this delay if you want maximum sampling speed.
  delay(5); 
}