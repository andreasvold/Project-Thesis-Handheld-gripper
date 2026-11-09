#include <Arduino.h>
#include "config.h"
#include "sensor.h"
#include "accel_mma8452.h"
#include "piezo.h"
#include "debug_capture.h"

namespace {
constexpr uint8_t MAX_SENSORS = 8;
Sensor* g_sensors[MAX_SENSORS];
uint8_t g_sensorCount = 0;
String  g_cmd;
}

// Takes ownership of s. Keeps it only if the hardware initialises.
void addSensor(Sensor* s) {
  if (!s) return;
  if (g_sensorCount >= MAX_SENSORS) { delete s; return; }
  if (!s->begin()) {
    Serial.print(F("[WARN] not found / failed: "));
    Serial.println(s->name());
    delete s;
    return;
  }
  g_sensors[g_sensorCount++] = s;
  Serial.print(F("[OK] "));
  s->printInfo(Serial);
}

// The only place that knows which sensors exist.
void registerSensors() {
  if (ENABLE_ACCEL) addSensor(new AccelMMA8452());
  if (ENABLE_PIEZO) addSensor(new PiezoSensor());
  // To add a sensor: write its module, add a flag to config.h, then:
  // if (ENABLE_MYSENSOR) addSensor(new MySensor());
}

void printHelp() {
  Serial.println(F("Commands: capture | status | help"));
}

void printStatus() {
  Serial.println(F("#STATUS_BEGIN"));
  Serial.print(F("uptime_ms=")); Serial.println(millis());
  Serial.print(F("free_heap=")); Serial.println(ESP.getFreeHeap());
  Serial.print(F("capture_samples=")); Serial.println(CAPTURE_SAMPLES);
  Serial.print(F("sensors=")); Serial.println(g_sensorCount);
  for (uint8_t i = 0; i < g_sensorCount; i++) {
    Serial.print(F("#SENSOR_STATUS "));
    g_sensors[i]->printInfo(Serial);
  }
  Serial.println(F("#STATUS_END"));
}

void runCommand(const String& cmd) {
  if (cmd == "capture")       runDebugCapture(g_sensors, g_sensorCount);
  else if (cmd == "status")   printStatus();
  else if (cmd == "help")     printHelp();
  else {
    Serial.print(F("unknown command: "));
    Serial.println(cmd);
  }
}

void handleSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      g_cmd.trim();
      if (g_cmd.length() > 0) runCommand(g_cmd);
      g_cmd = "";
    } else {
      g_cmd += c;
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  uint32_t t = millis();
  while (!Serial && millis() - t < 2000) delay(10);   // native USB: wait for host (max 2 s)

  registerSensors();
  Serial.println(F("#READY"));
  printHelp();
}

void loop() {
  // Idle: wait for commands. Sensors only sample during a capture.
  // A future "run" mode would call update() on each sensor here.
  handleSerial();
}