import time
import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports
from matplotlib.animation import FuncAnimation

# --- Configuration ---
BAUD_RATE = 250000  # High baud rate for fast streaming
MAX_SAMPLES = 1000  # Number of samples visible on screen at once
V_REF = 5.0
ACCEL_SCALE = 1024.0  # 1024 counts = 1g for ±2g range

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

ser = serial.Serial(port, BAUD_RATE, timeout=0.001)
print(f"Connected to {port} at {BAUD_RATE} baud.")

# --- Setup Multi-Panel Figure (2 Subplots) ---
fig, (ax_slider, ax_acc) = plt.subplots(
    2, 1, figsize=(10, 6), sharex=True
)

# Initialize data buffers
slider_data = [0.0] * MAX_SAMPLES
acc_data = [0.0] * MAX_SAMPLES

# Create line objects
(line_slider,) = ax_slider.plot(
    slider_data, color="mediumseagreen", linewidth=1.2
)
(line_acc,) = ax_acc.plot(
    acc_data, color="dodgerblue", linewidth=1.0
)

# Configure axes labels & limits
ax_slider.set_title("1. Slider Potentiometer Position")
ax_slider.set_ylabel("Voltage (V)")
ax_slider.set_ylim(-0.1, V_REF + 0.1)
ax_slider.grid(True, linestyle="--", alpha=0.5)

ax_acc.set_title("2. Accelerometer Z-Axis (Hardware High-Pass Filtered)")
ax_acc.set_ylabel("Acceleration (g)")
ax_acc.set_xlabel("Recent Samples")
ax_acc.set_ylim(-0.5, 0.5)  # Zoomed view for vibration/slip detection (adjust as needed)
ax_acc.grid(True, linestyle="--", alpha=0.5)

# Performance tracking
count = 0
t_start = time.time()


def update(_frame):
    global slider_data, acc_data, count, t_start

    new_sliders = []
    new_accs = []

    # Drain the serial buffer entirely to prevent lag
    while ser.in_waiting:
        try:
            line_str = ser.readline().decode("ascii", errors="ignore").strip()
            if "," in line_str:
                parts = line_str.split(",")
                if len(parts) >= 2:
                    s_val = float(parts[0])
                    acc_val = float(parts[1])

                    new_sliders.append((s_val / 1023.0) * V_REF)
                    new_accs.append(acc_val / ACCEL_SCALE)  # Convert raw counts to g
        except ValueError:
            continue

    if new_accs:
        # Update Slider buffer
        slider_data.extend(new_sliders)
        slider_data = slider_data[-MAX_SAMPLES:]
        line_slider.set_ydata(slider_data)

        # Update Accelerometer buffer
        acc_data.extend(new_accs)
        acc_data = acc_data[-MAX_SAMPLES:]
        line_acc.set_ydata(acc_data)

        # Calculate and print actual loop sample rate
        count += len(new_accs)
        elapsed = time.time() - t_start
        if elapsed >= 1.0:
            print(f"Streaming sample rate: {count / elapsed:.0f} Hz")
            count = 0
            t_start = time.time()

    return line_slider, line_acc


# Run animation with a fast refresh interval (10ms)
ani = FuncAnimation(
    fig, update, interval=10, blit=True, cache_frame_data=False
)

plt.tight_layout()
try:
    plt.show()
finally:
    ser.close()