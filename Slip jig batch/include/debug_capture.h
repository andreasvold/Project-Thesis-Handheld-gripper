#pragma once
#include "sensor.h"

// Records CAPTURE_SAMPLES per sensor into RAM, then dumps everything over Serial.
// Each sensor stops when its buffer is full; the capture ends when all are done
// (or on timeout).
void runDebugCapture(Sensor* const* sensors, uint8_t count);