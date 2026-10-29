import time
import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports
from matplotlib.animation import FuncAnimation
from scipy.signal import butter, lfilter, lfilter_zi

# --- Configuration ---
BAUD_RATE = 250000  # Increased baud rate for dual-sensor high-speed stream
MAX_SAMPLES = 1000  # Number of samples visible on screen at once
V_REF = 5.0

# --- High-pass filter settings for the Piezo sensor ---
FS = 2500.0  # Estimated sample rate in Hz
HP_CUTOFF = 100.0  # Frequencies below this are attenuated (Hz)
HP_ORDER = 2
Y_LIM_PIEZO = 0.5  # Zoom level for high-passed vibration view

# Filter coefficients
b, a = butter(HP_ORDER, HP_CUTOFF / (FS / 2), btype="highpass")
zi = None  # Filter state


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

# --- Setup Multi-Panel Figure (3 Subplots) ---
fig, (ax_slider, ax_raw_piezo, ax_hp_piezo) = plt.subplots(
    3, 1, figsize=(10, 7), sharex=True
)

# Initialize data buffers
slider_data = [0.0] * MAX_SAMPLES
raw_piezo_data = [0.0] * MAX_SAMPLES
hp_piezo_data = [0.0] * MAX_SAMPLES

# Create line objects
(line_slider,) = ax_slider.plot(
    slider_data, color="mediumseagreen", linewidth=1.2
)
(line_raw_piezo,) = ax_raw_piezo.plot(
    raw_piezo_data, color="orange", linewidth=1.0
)
(line_hp_piezo,) = ax_hp_piezo.plot(
    hp_piezo_data, color="dodgerblue", linewidth=1.0
)

# Configure axes labels & limits
ax_slider.set_title("1. Slider Potentiometer Position")
ax_slider.set_ylabel("Voltage (V)")
ax_slider.set_ylim(-0.1, V_REF + 0.1)
ax_slider.grid(True, linestyle="--", alpha=0.5)

ax_raw_piezo.set_title("2. Raw Vibration Sensor (Piezo)")
ax_raw_piezo.set_ylabel("Voltage (V)")
ax_raw_piezo.set_ylim(-0.1, V_REF + 0.1)
ax_raw_piezo.grid(True, linestyle="--", alpha=0.5)

ax_hp_piezo.set_title(
    f"3. High-Passed Vibration (Cutoff: {HP_CUTOFF:g} Hz) - Micro-Slip/Stick-Slip"
)
ax_hp_piezo.set_ylabel("Filtered (V)")
ax_hp_piezo.set_xlabel("Recent Samples")
ax_hp_piezo.set_ylim(-Y_LIM_PIEZO, Y_LIM_PIEZO)
ax_hp_piezo.grid(True, linestyle="--", alpha=0.5)

# Performance tracking
count = 0
t_start = time.time()


def update(_frame):
    global slider_data, raw_piezo_data, hp_piezo_data, zi, count, t_start

    new_sliders = []
    new_piezos = []

    # Drain the serial buffer entirely to prevent lag
    while ser.in_waiting:
        try:
            line_str = ser.readline().decode("ascii", errors="ignore").strip()
            if "," in line_str:
                parts = line_str.split(",")
                if len(parts) >= 2:
                    s_val = float(parts[0])
                    p_val = float(parts[1])

                    new_sliders.append((s_val / 1023.0) * V_REF)
                    new_piezos.append((p_val / 1023.0) * V_REF)
        except ValueError:
            continue

    if new_piezos:
        x_piezo = np.asarray(new_piezos)

        # Initialize filter state if needed
        if zi is None:
            zi = lfilter_zi(b, a) * x_piezo[0]

        filtered, zi = lfilter(b, a, x_piezo, zi=zi)

        # Update Slider buffer
        slider_data.extend(new_sliders)
        slider_data = slider_data[-MAX_SAMPLES:]
        line_slider.set_ydata(slider_data)

        # Update Raw Piezo buffer
        raw_piezo_data.extend(new_piezos)
        raw_piezo_data = raw_piezo_data[-MAX_SAMPLES:]
        line_raw_piezo.set_ydata(raw_piezo_data)

        # Update High-Passed Piezo buffer
        hp_piezo_data.extend(filtered.tolist())
        hp_piezo_data = hp_piezo_data[-MAX_SAMPLES:]
        line_hp_piezo.set_ydata(hp_piezo_data)

        # Calculate and print actual loop sample rate
        count += len(new_piezos)
        elapsed = time.time() - t_start
        if elapsed >= 1.0:
            print(f"Streaming sample rate: {count / elapsed:.0f} Hz")
            count = 0
            t_start = time.time()

    return line_slider, line_raw_piezo, line_hp_piezo


# Run animation with a fast refresh interval (10ms)
ani = FuncAnimation(
    fig, update, interval=10, blit=True, cache_frame_data=False
)

plt.tight_layout()
try:
    plt.show()
finally:
    ser.close()