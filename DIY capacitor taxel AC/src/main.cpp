// Capacitive taxel readout - Arduino Uno, raw node B waveform
// D9 outputs a steady square wave (Timer1). Each loop the Arduino
// captures N raw samples of node B and sends one line:
//
//   wave:<us per sample>:<v1>,<v2>,...,<vN>:<D9 states as 0/1 string>
//
// Values are raw ADC counts (0-1023 = 0-5 V); no filtering or averaging.
//
// Send 'x' over serial to switch the excitation off/on
// (useful to see node B's resting level).

#include <Arduino.h>
#include "CapSensor.h"

const uint16_t N = 100;        // samples per burst (~11 ms at ~112 us/sample)

uint16_t  samples[N];
uint8_t   levels[N];
CapSensor sensor;              // defaults: D9 at 500 Hz, A0 sense

void printExcitation() {
  Serial.print(F("# excitation: "));
  if (sensor.excitationRunning()) {
    Serial.print(sensor.exciteHz(), 1);
    Serial.println(F(" Hz"));
  } else {
    Serial.println(F("off"));
  }
}

void setup() {
  Serial.begin(115200);
  sensor.begin();
  delay(200);                  // let node A settle
  printExcitation();
}

void loop() {
  // Direct analog read on pin A0
  int val = analogRead(A0);

  // Print raw integer directly over serial
  Serial.println(val);
  //delayMicroseconds(1);
  delayMicroseconds(200);
}