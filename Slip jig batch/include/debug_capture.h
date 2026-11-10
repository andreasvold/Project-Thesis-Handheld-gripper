#pragma once
#include <Arduino.h>
#include "sensor.h"

// Non-blocking line reader for the USB serial port. Returns true and fills
// `line` (trimmed) once a complete line has arrived.
bool pollLine(String& line);

// Capture sequence:
//   ARM     waits for "go" (sensors idle, nothing recorded)
//   RECORD  from "go" until every buffer is full, "stop" arrives, or timeout
//   DUMP    sends the recorded data over serial
void runDebugCapture(Sensor* const* sensors, uint8_t count);