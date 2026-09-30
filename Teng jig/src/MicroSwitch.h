#ifndef MICRO_SWITCH_H
#define MICRO_SWITCH_H

#include <Arduino.h>

class MicroSwitch {
private:
    uint8_t _pin;
    bool _isNO;
    bool _lastRawState;
    bool _debouncedState;
    unsigned long _lastDebounceTime;
    unsigned long _debounceDelay;
    bool _wasPressedFlag;
    bool _wasReleasedFlag;

public:
    /**
     * @param pin The GPIO pin connected to the NO or NC terminal.
     * @param isNO Set true for Normally Open, false for Normally Closed.
     * @param debounceMs Debounce time in milliseconds (default: 50ms).
     */
    MicroSwitch(uint8_t pin, bool isNO = true, unsigned long debounceMs = 50);

    void begin();
    void update();
    bool isPressed() const;
    bool wasPressed();
    bool wasReleased();
};

#endif // MICRO_SWITCH_H