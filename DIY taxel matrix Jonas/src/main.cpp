#include <Arduino.h>

// Define Row and Column allocations
const int rowPins[] = {2, 3, 4, 5, 6, 7};
const int numRows = 6; // 6 physical drive rows

const int colPins[] = {A0, A1};
const int numCols = 2; // 2 physical sense channels

// 2D Array holding raw sensor data [6][2]
int fsrMatrix[numRows][numCols];

void printMatrix();

void setup() { 
  Serial.begin(115200); // Set to 115200 to match Python BAUD_RATE

  // Set all Row pins to INPUT mode initially to keep them isolated
  for (int r = 0; r < numRows; r++) {
    pinMode(rowPins[r], INPUT);
  }
}

void loop() {
  // Scan through each Row
  for (int r = 0; r < numRows; r++) {

    // Activate the current row by making it an OUTPUT driven HIGH
    pinMode(rowPins[r], OUTPUT);
    digitalWrite(rowPins[r], HIGH);

    // Small settling time delay for stable analog readings
    delayMicroseconds(10);

    // Read both column channels for this active row
    for (int c = 0; c < numCols; c++) {
      fsrMatrix[r][c] = analogRead(colPins[c]); // Value from 0 to 1023
    }

    // Deactivate the current row by resetting it back to INPUT
    digitalWrite(rowPins[r], LOW);
    pinMode(rowPins[r], INPUT);
  }

  // Print raw values formatted for Python parsing
  printMatrix();
  delay(50); // ~20 FPS refresh rate
}

void printMatrix() {
  // Transpose output to match Python (ROWS = 2, COLS = 6)
  // Print 2 lines total, each line containing 6 space-separated values
  for (int c = 0; c < numCols; c++) {
    for (int r = 0; r < numRows; r++) {
      Serial.print(fsrMatrix[r][c]);
      if (r < numRows - 1) {
        Serial.print(" "); // Single space delimiter between values
      }
    }
    Serial.println(); // End line for this row
  }
}