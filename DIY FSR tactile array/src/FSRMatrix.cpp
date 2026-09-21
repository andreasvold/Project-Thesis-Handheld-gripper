#include "FSRMatrix.h"

FSRMatrix::FSRMatrix(const uint8_t rowPins[NUM_ROWS], const uint8_t colPins[NUM_COLS]) {
    for (uint8_t r = 0; r < NUM_ROWS; r++) {
        _rowPins[r] = rowPins[r];
    }
    for (uint8_t c = 0; c < NUM_COLS; c++) {
        _colPins[c] = colPins[c];
    }
}

void FSRMatrix::begin() {
    // Set all rows to INPUT high-impedance mode initially
    for (uint8_t r = 0; r < NUM_ROWS; r++) {
        pinMode(_rowPins[r], INPUT);
    }
    // Set column pins to INPUT (ADC default)
    for (uint8_t c = 0; c < NUM_COLS; c++) {
        pinMode(_colPins[c], INPUT);
    }
}

void FSRMatrix::readMatrix() {
    for (uint8_t r = 0; r < NUM_ROWS; r++) {
        // Drive the active row HIGH
        pinMode(_rowPins[r], OUTPUT);
        digitalWrite(_rowPins[r], HIGH);

        // Small delay to let line voltages settle
        delayMicroseconds(20);

        // Read all column ADC values for this driven row
        for (uint8_t c = 0; c < NUM_COLS; c++) {
            _grid[r][c] = analogRead(_colPins[c]);
        }

        // Return row pin to INPUT (high impedance) to avoid crosstalk
        digitalWrite(_rowPins[r], LOW);
        pinMode(_rowPins[r], INPUT);
    }
}

uint16_t FSRMatrix::getValue(uint8_t row, uint8_t col) const {
    if (row >= NUM_ROWS || col >= NUM_COLS) return 0;
    return _grid[row][col];
}

void FSRMatrix::printGrid() const {
    Serial.println("START"); // Minimal fix: changed header to "START"
    for (uint8_t r = 0; r < NUM_ROWS; r++) {
        for (uint8_t c = 0; c < NUM_COLS; c++) {
            Serial.print(_grid[r][c]);
            Serial.print("\t");
        }
        Serial.println();
    }
    Serial.println();
}