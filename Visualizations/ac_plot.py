"""
Live view of the raw node B waveform from the capacitive taxel readout.

The Arduino sends lines of the form
    wave:<us per sample>:<v1>,<v2>,...:<D9 states as 0/1>
plus comment lines starting with '#'.

The plot shows node B in volts against time, with the D9 excitation
drawn faintly behind it so you can see how node B responds to each edge.

Keys (click the plot window first):
    x  -> switch the excitation on/off on the Arduino
    h  -> hold/resume the display (freeze a waveform to look at it)
"""

import re
import time

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial
import serial.tools.list_ports

BAUD_RATE = 9600      # must match Serial.begin() in main.cpp
VREF = 5.0            # ADC full scale in volts
ADC_MAX = 1023

# Free up keys that matplotlib uses for its own shortcuts
for key in ("x", "h"):
    for name, keys in plt.rcParams.items():
        if name.startswith("keymap.") and key in keys:
            plt.rcParams[name] = [k for k in keys if k != key]


# --- Automatic port selection ---
def get_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    for p in ports:
        if any(k in p.description for k in ["Arduino", "CH340", "USB", "Serial"]):
            print(f"Auto-selected: {p.device} ({p.description})")
            return p.device
    print(f"Defaulting to first available port: {ports[0].device}")
    return ports[0].device


SERIAL_PORT = get_arduino_port()
if not SERIAL_PORT:
    print("\n[ERROR] No active COM ports found.")
    print("1. Check if your Arduino USB cable is plugged in.")
    print("2. Make sure you installed the Arduino driver (e.g., CH340 / FT232R).")
    print("3. Check Device Manager under 'Ports (COM & LPT)'.")
    raise SystemExit(1)

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    time.sleep(2)  # the Uno resets when the port opens
    ser.reset_input_buffer()
    print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud\n")
except Exception as e:
    print(f"Error opening port {SERIAL_PORT}: {e}")
    raise SystemExit(1)


RE_WAVE = re.compile(r"wave:\s*([\d.]+):([\d,]+):([01]+)")

hold = False
excitation_text = ""

# --- Plot setup ---
fig, ax = plt.subplots(figsize=(9, 4.5))
line_d9, = ax.step([], [], where="post", color="gray", alpha=0.35,
                   linewidth=1.2, label="D9 excitation")
line_b, = ax.plot([], [], color="dodgerblue", linewidth=1.5,
                  marker=".", markersize=4, label="node B")
ax.set_title("Raw node B waveform")
ax.set_xlabel("Time (ms)")
ax.set_ylabel("Voltage (V)")
ax.set_ylim(-0.2, VREF + 0.2)
ax.grid(True, linestyle="--", alpha=0.5)
ax.legend(loc="upper right")
status = ax.text(0.01, 0.02, "", transform=ax.transAxes,
                 ha="left", va="bottom", fontsize=9, color="gray")


def show_frame(dt_us, values, bits):
    n = min(len(values), len(bits))
    if n == 0:
        return
    t_ms = [i * dt_us / 1000.0 for i in range(n)]
    volts = [v * VREF / ADC_MAX for v in values[:n]]
    d9 = [VREF if b == "1" else 0.0 for b in bits[:n]]

    line_b.set_data(t_ms, volts)
    line_d9.set_data(t_ms, d9)
    ax.set_xlim(0, t_ms[-1] + dt_us / 1000.0)

    vmin, vmax = min(volts), max(volts)
    mean = sum(volts) / n
    status.set_text(
        f"min {vmin:.2f} V   max {vmax:.2f} V   p-p {vmax - vmin:.2f} V   "
        f"mean {mean:.2f} V   {dt_us:.0f} µs/sample   {excitation_text}"
        + ("   [HOLD]" if hold else "")
    )


def update(_frame):
    global excitation_text
    latest = None

    while ser.in_waiting:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        if line.startswith("#"):
            print(line)
            if "excitation:" in line:
                excitation_text = "excitation " + line.split("excitation:", 1)[1].strip()
            continue
        m = RE_WAVE.search(line)
        if m:
            latest = m

    if latest and not hold:
        dt_us = float(latest.group(1))
        values = [int(v) for v in latest.group(2).split(",") if v]
        bits = latest.group(3)
        show_frame(dt_us, values, bits)

    return line_b, line_d9


def on_key(event):
    global hold
    if event.key == "x":
        ser.write(b"x")
    elif event.key == "h":
        hold = not hold


fig.canvas.mpl_connect("key_press_event", on_key)
ani = FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)

plt.tight_layout()
try:
    plt.show()
finally:
    ser.close()