#include <Arduino.h>
#include "config.h"
#include "sensor.h"
#include "accel_mma8452.h"
#include "piezo.h"
#include "capacitance_sensor.h"
#include "debug_capture.h"

namespace {
constexpr uint8_t MAX_SENSORS = 8;
Sensor* g_sensors[MAX_SENSORS];
uint8_t g_sensorCount = 0;
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
  if (ENABLE_CAPACITANCE) addSensor(new CapacitanceSensor());
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
  if (cmd == "capture")                        runDebugCapture(g_sensors, g_sensorCount);
  else if (cmd == "status")                    printStatus();
  else if (cmd == "help")                      printHelp();
  else if (cmd == "go" || cmd == "stop" ||
           cmd == "abort")                     { /* only meaningful during a capture */ }
  else {
    Serial.print(F("unknown command: "));
    Serial.println(cmd);
  }
}

void handleSerial() {
  String line;
  while (pollLine(line)) runCommand(line);
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
  handleSerial();
}