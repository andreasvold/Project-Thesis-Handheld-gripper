#include "MicroSwitch.h"

MicroSwitch::MicroSwitch(uint8_t pin, bool isNO, unsigned long debounceMs) 
    : _pin(pin), 
      _isNO(isNO), 
      _debounceDelay(debounceMs),
      _lastRawState(false), 
      _debouncedState(false), 
      _lastDebounceTime(0),
      _wasPressedFlag(false), 
      _wasReleasedFlag(false) {}

void MicroSwitch::begin() {
    pinMode(_pin, _isNO ? INPUT_PULLUP : INPUT);
    
    // Read initial pin state
    bool rawReading = digitalRead(_pin);
    _debouncedState = _isNO ? !rawReading : rawReading;
    _lastRawState = _debouncedState;
}

void MicroSwitch::update() {
    bool rawReading = digitalRead(_pin);
    bool currentRawState = _isNO ? !rawReading : rawReading;

    // Reset switch state change counter if raw state changed
    if (currentRawState != _lastRawState) {
        _lastDebounceTime = millis();
    }

    if ((millis() - _lastDebounceTime) > _debounceDelay) {
        // If state has changed after the debounce delay
        if (currentRawState != _debouncedState) {
            _debouncedState = currentRawState;

            if (_debouncedState) {
                _wasPressedFlag = true;
            } else {
                _wasReleasedFlag = true;
            }
        }
    }

    _lastRawState = currentRawState;
}

bool MicroSwitch::isPressed() const {
    return _debouncedState;
}

bool MicroSwitch::wasPressed() {
    if (_wasPressedFlag) {
        _wasPressedFlag = false;
        return true;
    }
    return false;
}

bool MicroSwitch::wasReleased() {
    if (_wasReleasedFlag) {
        _wasReleasedFlag = false;
        return true;
    }
    return false;
}