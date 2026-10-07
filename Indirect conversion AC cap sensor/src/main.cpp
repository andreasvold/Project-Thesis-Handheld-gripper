#include <Arduino.h>
#include "ChargeAmpSensor.h"

ChargeAmpSensor sensor;

void setup() {
  Serial.begin(115200);

  sensor.cfg.feedbackCap_pF = 1;   // set to your actual C
  sensor.cfg.adcPrescaler   = 32;     // 32 is a good speed/accuracy compromise
  sensor.begin();

  Serial.println(F("Taring: keep the sensor unloaded..."));
  sensor.tare(256);
  Serial.println(F("counts,volts,deltaC_pF"));
}

void loop() {
  const uint16_t N = 8; // Reduced from 64 to speed up reading rate
  float counts = sensor.readCounts(N);
  float volts  = sensor.readVolts(N);
  float dPf    = sensor.readDeltaPf(N);
  
  Serial.print(counts, 2);
  Serial.print(',');
  Serial.print(volts, 4);
  Serial.print(',');
  Serial.println(dPf, 4);
}