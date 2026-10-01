// Capacitive taxel readout - Arduino Uno, raw node B waveform
//
// Wiring:
//   D9  -> C_ref (few pF) -> node A
//   node A -> sensor inner plate; sensor outer plate -> GND
//   node A -> 10 MOhm -> 5V and node A -> 10 MOhm -> GND
//   node A -> OPA340 pin 3; pin 2 tied to pin 6; pin 6 -> A0
//   OPA340 pin 7 -> 5V, pin 4 -> GND, 100 nF across 7 and 4
//
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
  Serial.begin(9600);
  sensor.begin();
  delay(200);                  // let node A settle
  printExcitation();
}

void loop() {
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 'x') {
      if (sensor.excitationRunning()) sensor.stopExcitation();
      else                            sensor.startExcitation();
      printExcitation();
    }
  }

  float dt = sensor.capture(samples, levels, N);

  Serial.print(F("wave:"));
  Serial.print(dt, 1);
  Serial.print(':');
  for (uint16_t i = 0; i < N; i++) {
    if (i) Serial.print(',');
    Serial.print(samples[i]);
  }
  Serial.print(':');
  for (uint16_t i = 0; i < N; i++) {
    Serial.print(levels[i] ? '1' : '0');
  }
  Serial.println();
}