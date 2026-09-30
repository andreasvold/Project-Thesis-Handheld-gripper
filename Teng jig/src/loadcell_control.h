#ifndef LOADCELL_CONTROL_H
#define LOADCELL_CONTROL_H

#include <Arduino.h>

extern volatile bool loadcell_ready;  // true once tare is finished
long getLoad();                       // atomic read of the latest load value

void vLoadCellTask(void *pvParameters);

#endif