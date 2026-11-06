import time
import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports
from matplotlib.animation import FuncAnimation

# --- Configuration ---
BAUD_RATE = 115200  # Matches Arduino Serial.begin(115200)
MAX_SAMPLES = 500   # Number of samples visible on screen at once
V_REF = 5.0

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

# --- Setup Single-Panel Figure ---
fig, ax = plt.subplots(figsize=(10, 5))

# Initialize data buffer
data_buffer = [0.0] * MAX_SAMPLES

# Create line object
(line,) = ax.plot(data_buffer, color="darkorange", linewidth=1.5)

# Configure axes labels & limits
ax.set_title("Piezo Ultrasound Sensor - Peak Amplitude")
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Recent Samples")
ax.set_ylim(-0.1, V_REF + 0.1)
ax.grid(True, linestyle="--", alpha=0.5)

# Performance tracking
count = 0
t_start = time.time()

def update(_frame):
    global data_buffer, count, t_start

    new_values = []

    # Drain the serial buffer entirely to prevent lag
    while ser.in_waiting:
        try:
            line_str = ser.readline().decode("ascii", errors="ignore").strip()
            if line_str:
                val = float(line_str)
                # Convert ADC (0-1023) to Voltage
                voltage = (val / 1023.0) * V_REF
                new_values.append(voltage)
        except ValueError:
            continue

    if new_values:
        data_buffer.extend(new_values)
        data_buffer = data_buffer[-MAX_SAMPLES:]
        line.set_ydata(data_buffer)

        # Calculate and print actual loop sample rate
        count += len(new_values)
        elapsed = time.time() - t_start
        if elapsed >= 1.0:
            print(f"Streaming sample rate: {count / elapsed:.0f} Hz")
            count = 0
            t_start = time.time()

    return line,

# Run animation with a fast refresh interval (10ms)
ani = FuncAnimation(fig, update, interval=10, blit=True, cache_frame_data=False)

plt.tight_layout()
try:
    plt.show()
finally:
    ser.close()