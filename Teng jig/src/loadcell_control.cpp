#include <Arduino.h>
#include <Arduino_FreeRTOS.h>
#include <util/atomic.h>
#include "HX711.h"
#include "loadcell_control.h"

const int LOADCELL_DOUT_PIN = 4;
const int LOADCELL_SCK_PIN  = 2;

const uint8_t TARE_SAMPLES   = 20;  // 2 s at 10 SPS (was 100 = ~10 s)
const uint8_t PRINT_EVERY_N  = 10;  // print 1 in N readings

HX711 scale;
static volatile long current_load = 0;
volatile bool loadcell_ready = false;

// 32-bit values are not atomic on AVR, so guard every access.
long getLoad() {
  long v;
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { v = current_load; }
  return v;
}

// Average raw readings while sleeping between polls, instead of
// scale.tare(), which spin-waits inside the library.
static void tareYielding(uint8_t samples) {
  long sum = 0;
  uint8_t got = 0;
  while (got < samples) {
    if (scale.is_ready()) {
      sum += scale.read();
      got++;
    }
    vTaskDelay(1);
  }
  scale.set_offset(sum / samples);
}

void vLoadCellTask(void *pvParameters) {
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

  Serial.println(F("[LOADCELL] Waiting 2s for mechanical settling..."));
  vTaskDelay(pdMS_TO_TICKS(2000));

  Serial.println(F("[LOADCELL] Taring..."));
  tareYielding(TARE_SAMPLES);
  loadcell_ready = true;
  Serial.println(F("[LOADCELL] Scale ready."));

  uint8_t printCount = 0;
  for (;;) {
    if (scale.is_ready()) {
      long v = scale.get_value(1);
      ATOMIC_BLOCK(ATOMIC_RESTORESTATE) { current_load = v; }

      if (++printCount >= PRINT_EVERY_N) {
        printCount = 0;
        Serial.print(F("[LOADCELL] Reading: "));
        Serial.println(v);
      }
    }
    vTaskDelay(1);  // one tick (~16 ms); HX711 makes 10 samples/s by default
  }
}