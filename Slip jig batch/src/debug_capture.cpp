#include "debug_capture.h"

void runDebugCapture(Sensor* const* sensors, uint8_t count) {
  if (count == 0) {
    Serial.println(F("#CAPTURE_ERROR no sensors enabled"));
    return;
  }

  const uint32_t t0 = micros();
  for (uint8_t i = 0; i < count; i++) sensors[i]->arm(t0);

  Serial.print(F("#CAPTURE_BEGIN samples_per_sensor="));
  Serial.println(CAPTURE_SAMPLES);

  const uint32_t startMs = millis();
  bool timedOut = false;

  for (;;) {
    bool allDone = true;
    for (uint8_t i = 0; i < count; i++) {
      if (!sensors[i]->captureDone()) {
        sensors[i]->update(micros());
        allDone = false;
      }
    }
    if (allDone) break;
    if (millis() - startMs > CAPTURE_TIMEOUT_MS) { timedOut = true; break; }
  }

  if (timedOut) Serial.println(F("#CAPTURE_TIMEOUT"));
  Serial.print(F("#CAPTURE_ELAPSED_MS "));
  Serial.println(millis() - startMs);

  for (uint8_t i = 0; i < count; i++) sensors[i]->dump(Serial);

  Serial.println(F("#CAPTURE_END"));
}