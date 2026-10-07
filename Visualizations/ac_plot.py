import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

BAUD_RATE = 115200
MAX_SAMPLES = 500  # Number of samples visible on screen at once
V_REF = 2.5        # Set to 3.3 if using a 3.3V board/reference

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

ax.set_title("Real-Time Voltage Reading (A0)")
ax.set_ylabel("Voltage (V)")
ax.set_xlabel("Recent Samples")
ax.set_ylim(-0.2, V_REF + 0.2)
ax.grid(True, linestyle="--", alpha=0.5)


def update(_frame):
    global y_data
    updated = False

    # Flush the serial buffer and append new values
    while ser.in_waiting:
        try:
            line_str = ser.readline().decode("ascii", errors="ignore").strip()
            
            # Extract ADC count or handle comma-separated strings (e.g. from ChargeAmpSensor)
            if "," in line_str:
                raw_val = float(line_str.split(",")[0])
            else:
                raw_val = float(line_str)

            # Convert 10-bit ADC value (0-1023) to Voltage
            GAIN = 10.0  # 10x software boost
            voltage = ((raw_val / 1023.0) * V_REF) * GAIN
            
            y_data.append(voltage)
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