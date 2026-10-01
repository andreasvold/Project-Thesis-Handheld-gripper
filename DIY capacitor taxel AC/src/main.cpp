// Capacitive taxel readout - Arduino Uno
//
// Wiring:
//   D9  -> C_ref (few pF) -> node A
//   node A -> sensor inner plate; sensor outer plate -> GND
//   node A -> 10 MOhm -> 5V and node A -> 10 MOhm -> GND
//   node A -> OPA340 pin 3; pin 2 tied to pin 6; pin 6 -> A0
//   OPA340 pin 7 -> 5V, pin 4 -> GND, 100 nF across 7 and 4
//
// Output (115200 baud, Serial Plotter friendly):
//   raw:<step size> delta:<raw - baseline>
// With the sensor in the "C2" position (one plate grounded),
// pressing makes raw go DOWN, so delta becomes negative.
//
// Send 'c' over serial to recalibrate the baseline (sensor untouched).

#include <Arduino.h>
#include "CapSensor.h"

CapSensor sensor;   // defaults: D9 excitation, A0 sense, 64 cycles

void setup() {
  Serial.begin(9600);
  sensor.begin();

  delay(200);                              // let node A settle at 2.5 V
  float base = sensor.calibrate();
  Serial.print(F("# baseline: "));
  Serial.println(base);
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'c') {
      float base = sensor.calibrate();
      Serial.print(F("# baseline: "));
      Serial.println(base);
    }
  }

  float raw = sensor.measure();

  Serial.print(F("raw:"));
  Serial.print(raw);
  Serial.print(F(" delta:"));
  Serial.println(sensor.delta(raw));
}