#include <CapacitiveSensor.h>

// Replace 4 and 2 with your actual Send and Receive pins!
// CapacitiveSensor cs(sendPin, receivePin)
CapacitiveSensor cs = CapacitiveSensor(7, 8); 

void setup() {
  Serial.begin(9600);
  cs.set_CS_AutocaL_Millis(0xFFFFFFFF); // Disable auto-calibration reset
}

void loop() {
  long calValue = cs.capacitiveSensor(30);
  long rawValue = cs.capacitiveSensorRaw(30);

  Serial.print("Calibrated Value: ");
  Serial.print(calValue);
  Serial.print("  |  Raw Value: ");
  Serial.println(rawValue);

}