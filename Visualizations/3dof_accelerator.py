import time

import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports
from matplotlib.animation import FuncAnimation
from scipy.signal import butter, lfilter, lfilter_zi

BAUD_RATE = 250000
MAX_SAMPLES = 1000  # Number of samples visible on screen at once
COUNTS_PER_G = 1024.0  # MMA8452Q in the +/-2 g range: 1024 counts = 1 g

# --- Sensor settings (must match main.cpp) ---
FS = 800.0  # Output data rate of the accelerometer (Hz)
Y_LIM = 0.5  # Plot range is +/- Y_LIM g around zero

# --- Optional extra high-pass filter ---
# The chip's own high-pass (~16 Hz) already removes gravity, so this is off.
# Turn it on for a higher cutoff, e.g. to keep only slip vibrations and
# ignore slower movement of the gripper itself.
USE_HP = False
HP_CUTOFF = 50.0  # Frequencies below this are attenuated (Hz)
HP_ORDER = 2  # Higher = steeper roll-off

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

ser = serial.Serial(port, BAUD_RATE, timeout=0)
print(f"Connected to {port} at {BAUD_RATE} baud.")

# --- Setup Fast Plot ---
fig, ax = plt.subplots(figsize=(8, 4))
t_axis = (np.arange(MAX_SAMPLES) - (MAX_SAMPLES - 1)) / FS  # seconds, 0 = newest
y_data = [0.0] * MAX_SAMPLES
(line,) = ax.plot(t_axis, y_data, color="dodgerblue", linewidth=1.5)

title = "Z Acceleration (MMA8452Q)"
if USE_HP:
  title += f", extra high-pass {HP_CUTOFF:g} Hz"
ax.set_title(title)
ax.set_ylabel("Acceleration (g, gravity removed)")
ax.set_xlabel("Time (s)")
ax.set_xlim(t_axis[0], t_axis[-1])
ax.set_ylim(-Y_LIM, Y_LIM)
ax.grid(True, linestyle="--", alpha=0.5)

# For measuring the real sample rate
count = 0
t_start = time.time()

# Bytes received but not yet ending in a newline
rx_buffer = b""


def update(_frame):
  global y_data, zi, count, t_start, rx_buffer

  # Grab everything waiting; keep a half-received line for next frame
  rx_buffer += ser.read(ser.in_waiting)
  *lines, rx_buffer = rx_buffer.split(b"\n")

  new_g = []
  for raw in lines:
    try:
      counts = int(raw.strip())
    except ValueError:
      continue  # e.g. garbage right after the Arduino resets

    if -2048 <= counts <= 2047:  # valid 12-bit range
      new_g.append(counts / COUNTS_PER_G)

  if new_g:
    x = np.asarray(new_g)

    if USE_HP:
      # Start the filter at steady state so there's no startup spike
      if zi is None:
        zi = lfilter_zi(b, a) * x[0]
      x, zi = lfilter(b, a, x, zi=zi)

    y_data.extend(x.tolist())
    y_data = y_data[-MAX_SAMPLES:]
    line.set_ydata(y_data)

    # Report the actual sample rate once per second (should be ~800 Hz)
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