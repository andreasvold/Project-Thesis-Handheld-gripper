#include "debug_capture.h"

// ---------------------------------------------------------------------
// Non-blocking line reader. Returns true once a complete, non-empty line
// has arrived (trimmed). Call it as often as needed.
// ---------------------------------------------------------------------
bool pollLine(String& line) {
  static String buf;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c != '\n' && c != '\r') {
      buf += c;
      continue;
    }
    String complete = buf;
    buf = "";
    complete.trim();
    if (complete.length() > 0) {
      line = complete;
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------
static void printProgress(Sensor* const* sensors, uint8_t count, uint32_t elapsedMs) {
  Serial.print(F("#PROGRESS elapsed_ms="));
  Serial.print(elapsedMs);
  for (uint8_t i = 0; i < count; i++) {
    Serial.print(' ');
    Serial.print(sensors[i]->name());
    Serial.print('=');
    Serial.print(sensors[i]->count());
  }
  Serial.println();
}

void runDebugCapture(Sensor* const* sensors, uint8_t count) {
  if (count == 0) {
    Serial.println(F("#CAPTURE_ERROR no sensors enabled"));
    return;
  }

  String line;

  // ---- 1. ARM: nothing is sampled yet. Wait for "go". ----
  Serial.print(F("#ARMED samples_per_sensor="));
  Serial.println(CAPTURE_SAMPLES);
  Serial.println(F("#ARMED send 'go' to start, 'abort' to cancel"));

  for (;;) {
    if (pollLine(line)) {
      if (line == "go") break;
      if (line == "abort") {
        Serial.println(F("#CAPTURE_ABORTED"));
        return;
      }
    }
  }

  // ---- 2. START: this is t = 0 for every sensor. ----
  const uint32_t t0 = micros();
  const uint32_t startMs = millis();
  for (uint8_t i = 0; i < count; i++) sensors[i]->arm(t0);
  Serial.print(F("#RECORDING_START t_ms="));
  Serial.println(startMs);

  // ---- 3. RECORD until all buffers are full, "stop", or timeout. ----
  const char* reason = "full";
  uint32_t lastProgressMs = startMs;
  for (;;) {
    bool allDone = true;
    for (uint8_t i = 0; i < count; i++) {
      if (!sensors[i]->captureDone()) {
        sensors[i]->update(micros());
        allDone = false;
      }
    }
    if (allDone) break;

    if (pollLine(line) && line == "stop") {
      reason = "stop";
      break;
    }

    const uint32_t nowMs = millis();
    if (nowMs - startMs > CAPTURE_TIMEOUT_MS) {
      reason = "timeout";
      break;
    }
    if (nowMs - lastProgressMs >= PROGRESS_PERIOD_MS) {
      lastProgressMs = nowMs;
      printProgress(sensors, count, nowMs - startMs);
    }
  }

  const uint32_t elapsedMs = millis() - startMs;
  Serial.print(F("#RECORDING_END reason="));
  Serial.print(reason);
  Serial.print(F(" elapsed_ms="));
  Serial.println(elapsedMs);

  // ---- 4. DUMP: recorded data is sent only after recording ends. ----
  Serial.println(F("#DUMP_BEGIN"));
  for (uint8_t i = 0; i < count; i++) sensors[i]->dump(Serial);
  Serial.println(F("#CAPTURE_END"));
}