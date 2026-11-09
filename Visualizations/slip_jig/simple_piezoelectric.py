import matplotlib.pyplot as plt
import serial

# ==========================================
# CONFIGURATION (Update port as needed)
# ==========================================
PORT = "COM9"  # Use '/dev/ttyUSB0' or '/dev/cu.usbserial-*' for Linux/Mac
BAUD_RATE = 115200

# Initialize serial connection
print(f"Connecting to {PORT} at {BAUD_RATE} baud...")
ser = serial.Serial(PORT, BAUD_RATE, timeout=1)

# Setup real-time matplotlib plot
plt.ion()
fig, ax = plt.subplots(figsize=(10, 5))

x_data = []
y_data = []

(line,) = ax.plot([], [], "b-", label="Piezo Sensor (ADC)")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Sensor Value")
ax.set_title("Real-Time Piezo Sensor Monitor")
ax.legend()
ax.grid(True)

print("Plotting started. Press Ctrl+C in the terminal to exit.")

try:
  while True:
    raw_line = ser.readline()
    if not raw_line:
      continue

    line_str = raw_line.decode("utf-8", errors="ignore").strip()

    # Skip header row or empty lines
    if not line_str or "t_us" in line_str:
      continue

    # CSV Format from Arduino: t_us,ax,ay,az,piezo,piezo_pp
    parts = line_str.split(",")
    if len(parts) >= 6:
      try:
        t_us = int(parts[0])
        piezo_val = int(parts[4])  # Index 4 is the 'piezo' value

        # Convert microseconds to seconds
        t_sec = t_us / 1e6

        x_data.append(t_sec)
        y_data.append(piezo_val)

        # Keep a rolling window of the last 300 points for performance
        max_points = 300
        if len(x_data) > max_points:
          x_data.pop(0)
          y_data.pop(0)

        # Update plot data
        line.set_xdata(x_data)
        line.set_ydata(y_data)

        ax.relim()
        ax.autoscale_view()

        plt.draw()
        plt.pause(0.001)

      except ValueError:
        # Ignore malformed CSV lines
        pass

except KeyboardInterrupt:
  print("\nStopping...")
finally:
  ser.close()
  plt.ioff()
  plt.show()