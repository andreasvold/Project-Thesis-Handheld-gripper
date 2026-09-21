#ifndef FSR_MATRIX_H
#define FSR_MATRIX_H

#include <Arduino.h>

class FSRMatrix {
public:
    static const uint8_t NUM_ROWS = 4;
    static const uint8_t NUM_COLS = 4;

    FSRMatrix(const uint8_t rowPins[NUM_ROWS], const uint8_t colPins[NUM_COLS]);
    
    void begin();
    void readMatrix();
    
    // Returns raw ADC value (0-1023) for a specific cell
    uint16_t getValue(uint8_t row, uint8_t col) const;
    
    // Prints a visual grid to the Serial monitor
    void printGrid() const;

private:
    uint8_t _rowPins[NUM_ROWS];
    uint8_t _colPins[NUM_COLS];
    uint16_t _grid[NUM_ROWS][NUM_COLS];
};

#endif