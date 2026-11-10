# ESP32-C6 sensor debug firmware

Modular PlatformIO project for recording sensor data in a debug capture and plotting it on the PC.

## Layout

```
platformio.ini
include/
  config.h           all settings: enable flags, rates, pins, capture length
  sensor.h           Sensor interface, CaptureBuffer, SensorT<CH> base class
  accel_mma8452.h    accelerometer driver (MMA8452Q / MMA8451Q)
  piezo.h            piezo ADC driver
  debug_capture.h    capture + dump routine
src/
  main.cpp           sensor registry, serial command handling
  accel_mma8452.cpp
  piezo.cpp
  debug_capture.cpp
tools/
  capture.py         send "capture" to the board, save the dump to tools/captures/
  plot_capture.py    parse a capture, plot all or selected sensors, print statistics
```

## Quick start

1. Set options in `include/config.h` (sensors on/off, accelerometer ODR, piezo rate, `CAPTURE_SAMPLES`).
2. Build and upload: `pio run -t upload`
3. Close any serial monitor, then run `python tools/capture.py` (add the port if auto-detect fails).
4. Plot: `python tools/plot_capture.py`

Python dependencies: `pip install pyserial matplotlib numpy`

Useful variants:
```
python tools/plot_capture.py --sensors piezo
python tools/plot_capture.py --sensors accel --window 0 2
python tools/plot_capture.py --raw --save accel_raw.png --no-show
python tools/plot_capture.py --stats
python tools/capture.py --status
```

## Serial commands (for a terminal monitor)

- `capture`: record CAPTURE_SAMPLES per enabled sensor, then dump all of them
- `status`: free heap, enabled sensors and their settings
- `help`

## How a capture works

Every enabled sensor has its own RAM buffer and its own timestamps (microseconds since the capture started). Sensors run at their own rates, and a sensor stops once its buffer is full. The capture ends when all sensors are full or the timeout is reached. Because all sensors share one time origin, you can overlay them on a common time axis.

Dump format:
```
#CAPTURE_BEGIN samples_per_sensor=10000
#CAPTURE_ELAPSED_MS 25012
#SENSOR accel samples=10000 missed=0 overwritten=0 rate_hz=400.000 range_g=2 hpf=1 scale=0.0009765625 unit=g
t_us,ax,ay,az
0,12,-3,1019
...
#END accel
#SENSOR piezo samples=10000 missed=0 overwritten=0 rate_hz=2000 adc_bits=12 scale=0.0008058608 unit=V
t_us,value
...
#END piezo
#CAPTURE_END
```

`scale` and `unit` are written by each sensor, so the Python tools need no sensor-specific knowledge. Adding a new sensor does not require changing the plotting code.

## Reading the diagnostics

- `missed`: sample slots the scheduler could not serve, because the loop was too slow or the sensor was busy. This should be 0 for a reliable capture.
- `overwritten` (accelerometer): the sensor produced a new sample before the previous one was read. Lower the ODR or shorten the loop.
- `--stats` also shows the sample interval jitter. For a regular rate it should be tight. A large max or std means the timing is not reliable.

## Adding a sensor

1. Create `include/mysensor.h` and `src/mysensor.cpp`. Derive from `SensorT<N>` where N is the number of channels, and implement:
   - `begin()`: initialise the hardware, return false if it is not found
   - `update(nowUs)`: when `recording()` is true and a sample is due, read the hardware and call `record(nowUs, values)`
   - `onArm(t0Us)` (optional): reset your timers
   - `printMeta(out)`: write ` rate_hz=... scale=... unit=...` (leading space)
   - `channelName(c)`: column names
2. Add `constexpr bool ENABLE_MYSENSOR = true;` to `config.h`.
3. Add one line to `registerSensors()` in `main.cpp`.

## Notes and limitations

- Accelerometer timestamps are taken when the sample is read, not when the sensor produced it. The error is at most the poll interval (100 to 2000 us). For exact timing, wire INT1 to a GPIO and use an interrupt.
- `analogRead` is blocking and slower than a timer-driven ADC. Check the achieved piezo rate with `--stats` and lower `PIEZO_SAMPLE_RATE_HZ` if it is not reached.
- Piezo volts are an approximation based on `PIEZO_VREF_V`. The ESP32 ADC is not very linear. Use `analogReadMilliVolts()` if you need calibrated values.
- Memory: each sensor reserves `CAPTURE_SAMPLES * (4 + 2 * channels)` bytes. The default settings use about 160 KB. The `status` command prints the free heap.
- Per-sample RAM capture means data are only available after the capture ends. A continuous stream mode would be a separate addition.