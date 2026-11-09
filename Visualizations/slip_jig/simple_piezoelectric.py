import matplotlib.pyplot as plt
import serial

# ==========================================
# CONFIGURATION (Update port as needed)
# ==========================================
PORT = "COM9"  # Use '/dev/ttyUSB0' or '/dev/cu.usbserial-*' for Linux/Mac
BAUD_RATE = 115200  # must match SERIAL_BAUD in main.cpp
VREF = 3.3  # ADC reference voltage (approximate)
ADC_MAX = 4095.0  # 12-bit ADC
MAX_POINTS = 2000  # rolling window: 2000 points = 2 s at 1000 Hz
REDRAW_EVERY = 10  # redraw every N samples (drawing every sample is too slow)

# Initialize serial connection
print(f"Connecting to {PORT} at {BAUD_RATE} baud...")
ser = serial.Serial(PORT, BAUD_RATE, timeout=1)

# Setup real-time matplotlib plot
plt.ion()
fig, ax = plt.subplots(figsize=(10, 5))

t_data = []
v_data = []

(line,) = ax.plot([], [], "b-", label="Piezo Sensor (V)")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage (V)")
ax.set_title("Real-Time Piezo Sensor Monitor")
ax.legend()
ax.grid(True)

print("Plotting started. Press Ctrl+C in the terminal to exit.")

t0_us = None
sample_count = 0

try:
  while True:
    raw_line = ser.readline()
    if not raw_line:
      continue

    line_str = raw_line.decode("utf-8", errors="ignore").strip()

    # Skip header row or empty lines
    if not line_str or "t_us" in line_str:
      continue

    # CSV Format from firmware: t_us,piezo
    parts = line_str.split(",")
    if len(parts) >= 2:
      try:
        t_us = int(parts[0])
        piezo_value = int(parts[4])
        volts = piezo_value * VREF / ADC_MAX

        # Time starts at the first sample
        if t0_us is None:
          t0_us = t_us
        t_sec = (t_us - t0_us) / 1e6

        t_data.append(t_sec)
        v_data.append(volts)

        # Keep a rolling window of the last MAX_POINTS points
        if len(t_data) > MAX_POINTS:
          t_data.pop(0)
          v_data.pop(0)

        sample_count += 1
        if sample_count % REDRAW_EVERY == 0:
          line.set_data(t_data, v_data)

          ax.relim()
          ax.autoscale_view()

          plt.draw()
          plt.pause(0.001)

      except ValueError:
        # Ignore malformed lines
        pass

except KeyboardInterrupt:
  print("\nStopping...")
finally:
  ser.close()
  plt.ioff()
  plt.show()