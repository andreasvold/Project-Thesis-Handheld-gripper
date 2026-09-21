#include "FSRMatrix.h"

// Define pins for 4x4 matrix
const uint8_t ROW_PINS[4] = {2, 3, 4, 5};      // D2, D3, D4, D5
const uint8_t COL_PINS[4] = {A7, A6, A5, A4};  // Col1=A7, Col2=A6, Col3=A5, Col4=A4

FSRMatrix fsrMat(ROW_PINS, COL_PINS);

void setup() {
    // Baud Rate Mismatch: Ensure your Serial Monitor in PlatformIO (platformio.ini) 
    // or Arduino IDE is set to 115200 to match Serial.begin(115200) in your code.
    Serial.begin(9600);

    fsrMat.begin();
    Serial.println("FSR Matrix Initialized.");
}

void loop() {
    fsrMat.readMatrix();
    fsrMat.printGrid();
    delay(100);
}