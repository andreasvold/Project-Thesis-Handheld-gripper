import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

BAUD_RATE = 115200
MAX_SAMPLES = 500  # Number of samples visible on screen at once

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
y_data = [0] * MAX_SAMPLES
(line,) = ax.plot(y_data, color="dodgerblue", linewidth=1.5)

ax.set_title("Fast Raw Analog Input (A0)")
ax.set_ylabel("ADC Value (0–1023)")
ax.set_xlabel("Recent Samples")
ax.set_ylim(-10, 1034)
ax.grid(True, linestyle="--", alpha=0.5)


def update(_frame):
    global y_data
    updated = False

    # Flush the serial buffer and append new values
    while ser.in_waiting:
        try:
            val = int(ser.readline().decode("ascii", errors="ignore").strip())
            y_data.append(val)
            updated = True
        except ValueError:
            continue

    if updated:
        # Keep buffer fixed to MAX_SAMPLES length
        y_data = y_data[-MAX_SAMPLES:]
        line.set_ydata(y_data)

    return (line,)


ani = FuncAnimation(fig, update, interval=20, blit=True, cache_frame_data=False)

plt.tight_layout()
try:
    plt.show()
finally:
    ser.close()
