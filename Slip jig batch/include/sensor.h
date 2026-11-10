#pragma once
#include <Arduino.h>
#include "config.h"

// ---------------------------------------------------------------------
// Fixed-size RAM buffer for one sensor's capture.
// Each sample = timestamp (us since capture start) + CH int16 channels.
// ---------------------------------------------------------------------
template <uint8_t CH>
class CaptureBuffer {
public:
  void clear() { count_ = 0; }
  bool full() const { return count_ >= CAPTURE_SAMPLES; }
  uint32_t count() const { return count_; }

  void push(uint32_t tUs, const int16_t* values) {
    if (count_ >= CAPTURE_SAMPLES) return;
    t_[count_] = tUs;
    for (uint8_t c = 0; c < CH; c++) v_[count_][c] = values[c];
    count_++;
  }

  uint32_t timeAt(uint32_t i) const { return t_[i]; }
  int16_t  valueAt(uint32_t i, uint8_t c) const { return v_[i][c]; }

private:
  uint32_t t_[CAPTURE_SAMPLES];
  int16_t  v_[CAPTURE_SAMPLES][CH];
  uint32_t count_ = 0;
};

// ---------------------------------------------------------------------
// Abstract sensor. main.cpp only talks to this interface.
// ---------------------------------------------------------------------
class Sensor {
public:
  explicit Sensor(const char* name) : name_(name) {}
  virtual ~Sensor() {}

  const char* name() const { return name_; }

  virtual bool begin() = 0;                       // false = not found / not usable
  virtual void arm(uint32_t t0Us) = 0;            // start a capture (t0Us = micros() at start)
  virtual void update(uint32_t nowUs) = 0;        // call often; samples when due
  virtual bool captureDone() const = 0;           // true once CAPTURE_SAMPLES are stored
  virtual void printInfo(Print& out) const = 0;   // one status line
  virtual uint32_t count() const = 0;             // samples stored so far
  virtual void dump(Print& out) const = 0;        // "#SENSOR ... #END" block

protected:
  const char* name_;
};

// ---------------------------------------------------------------------
// Template base for sensors with CH channels. Handles the capture
// buffer, timestamps and the dump format, so a driver only has to
// read hardware and call record().
// ---------------------------------------------------------------------
template <uint8_t CH>
class SensorT : public Sensor {
public:
  using Sensor::Sensor;

  void arm(uint32_t t0Us) override {
    t0_ = t0Us;
    buf_.clear();
    missed_ = 0;
    overwritten_ = 0;
    running_ = true;
    onArm(t0Us);
  }

  bool captureDone() const override { return buf_.full(); }
  uint32_t count() const override { return buf_.count(); }

  void printInfo(Print& out) const override {
    out.print(name_);
    printMeta(out);
    out.println();
  }

  void dump(Print& out) const override {
    out.print(F("#SENSOR ")); out.print(name_);
    out.print(F(" samples=")); out.print(buf_.count());
    out.print(F(" missed=")); out.print(missed_);
    out.print(F(" overwritten=")); out.print(overwritten_);
    printMeta(out);
    out.println();

    out.print(F("t_us"));
    for (uint8_t c = 0; c < CH; c++) { out.print(','); out.print(channelName(c)); }
    out.println();

    for (uint32_t i = 0; i < buf_.count(); i++) {
      out.print(buf_.timeAt(i));
      for (uint8_t c = 0; c < CH; c++) { out.print(','); out.print(buf_.valueAt(i, c)); }
      out.println();
    }
    out.print(F("#END ")); out.println(name_);
  }

protected:
  virtual void onArm(uint32_t t0Us) { (void)t0Us; }
  virtual void printMeta(Print& out) const = 0;    // " key=value ..." (leading space!)
  virtual const char* channelName(uint8_t c) const = 0;

  bool recording() const { return running_ && !buf_.full(); }

  void record(uint32_t nowUs, const int16_t* values) {
    buf_.push(nowUs - t0_, values);
  }

  uint32_t missed_ = 0;        // scheduler skipped a sample slot (loop too slow)
  uint32_t overwritten_ = 0;   // sensor overwrote a sample before we read it

private:
  CaptureBuffer<CH> buf_;
  uint32_t t0_ = 0;
  bool running_ = false;
};