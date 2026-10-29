import time

import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports
from matplotlib.animation import FuncAnimation
from scipy.signal import butter, lfilter, lfilter_zi

BAUD_RATE = 115200
MAX_SAMPLES = 1000  # Number of samples visible on screen at once
V_REF = 1.1  # Set to 3.3 if using a 3.3V board/reference

# --- High-pass filter settings ---
FS = 2500.0  # Sample rate of the data stream in Hz (see note below)
HP_CUTOFF = 100.0  # Frequencies below this are attenuated (Hz)
HP_ORDER = 2  # Higher = steeper roll-off
Y_LIM = 0.5  # Plot range is +/- Y_LIM volts around zero

# Filter coefficients (must have HP_CUTOFF < FS / 2)
b, a = butter(HP_ORDER, HP_CUTOFF / (FS / 2), btype="highpass")
zi = None  # Filter state, initialized on the first sample


# --- Auto-detect Arduino Port ---
def get_port():
  ports = list(serial.tools.list_ports.comports())
  for p in ports:
    if any(k in p.description for k in ["Arduino", "CH340", "USB", "Serial"]):
      return p.device
  return ports[0].device if ports else None


port = get_port()
if not port:
  print("[ERROR] No serial port found.")
  raise SystemExit(1)

ser = serial.Serial(port, BAUD_RATE, timeout=0.01)
print(f"Connected to {port} at {BAUD_RATE} baud.")

# --- Setup Fast Plot ---
fig, ax = plt.subplots(figsize=(8, 4))
y_data = [0.0] * MAX_SAMPLES
(line,) = ax.plot(y_data, color="dodgerblue", linewidth=1.5)

ax.set_title(f"High-passed Voltage (A0), cutoff {HP_CUTOFF:g} Hz")
ax.set_ylabel("Voltage (V, DC removed)")
ax.set_xlabel("Recent Samples")
ax.set_ylim(-Y_LIM, Y_LIM)
ax.grid(True, linestyle="--", alpha=0.5)

# For measuring the real sample rate
count = 0
t_start = time.time()


def update(_frame):
  global y_data, zi, count, t_start
  new_volts = []

  # Flush the serial buffer and collect new values
  while ser.in_waiting:
    try:
      line_str = ser.readline().decode("ascii", errors="ignore").strip()

      if "," in line_str:
        raw_val = float(line_str.split(",")[0])
      else:
        raw_val = float(line_str)

      # Convert 10-bit ADC value (0-1023) to Voltage
      new_volts.append((raw_val / 1023.0) * V_REF)
    except ValueError:
      continue

  if new_volts:
    x = np.asarray(new_volts)

    # Start the filter at steady state so there's no startup spike
    if zi is None:
      zi = lfilter_zi(b, a) * x[0]

    filtered, zi = lfilter(b, a, x, zi=zi)

    y_data.extend(filtered.tolist())
    y_data = y_data[-MAX_SAMPLES:]
    line.set_ydata(y_data)

    # Report the actual sample rate once per second
    count += len(x)
    elapsed = time.time() - t_start
    if elapsed >= 1.0:
      print(f"Measured sample rate: {count / elapsed:.0f} Hz")
      count = 0
      t_start = time.time()

  return (line,)


ani = FuncAnimation(
    fig, update, interval=20, blit=True, cache_frame_data=False
)

plt.tight_layout()
try:
  plt.show()
finally:
  ser.close()