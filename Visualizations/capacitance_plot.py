import re
import time
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial
import serial.tools.list_ports

try:
    matplotlib.use('Qt5Agg')
except ImportError:
    pass

# --- Automatic Port Selection ---
def get_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None
    
    # Try to find a port with "Arduino" or "CH340" or "FTDI" in description
    for p in ports:
        if any(keyword in p.description for keyword in ["Arduino", "CH340", "USB", "Serial"]):
            print(f"Auto-selected: {p.device} ({p.description})")
            return p.device
            
    # Fallback to the first available port
    print(f"Defaulting to first available port: {ports[0].device}")
    return ports[0].device

SERIAL_PORT = get_arduino_port()
BAUD_RATE = 9600
MAX_POINTS = 200

if not SERIAL_PORT:
    print("\n[ERROR] No active COM ports found.")
    print("1. Check if your Arduino USB cable is plugged in.")
    print("2. Make sure you installed the Arduino driver (e.g., CH340 / FT232R).")
    print("3. Check Device Manager under 'Ports (COM & LPT)'.")
    exit(1)

# --- Open Serial Port ---
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    time.sleep(2)  # Allow Arduino time to reset
    print(f"Successfully connected to {SERIAL_PORT}\n")
except Exception as e:
    print(f"Error opening port {SERIAL_PORT}: {e}")
    exit(1)

# --- Data Buffers ---
x_data, cal_data, raw_data = [], [], []

# --- Plot Setup ---
fig, ax = plt.subplots(figsize=(8, 4))
line_cal, = ax.plot([], [], label='Calibrated Value', color='limegreen', linewidth=1.5)
#line_raw, = ax.plot([], [], label='Raw Value', color='dodgerblue', linewidth=1.5)

ax.set_title("Real-Time Capacitive Sensor Stream", fontsize=12)
ax.set_xlabel("Time Step")
ax.set_ylabel("Sensor Reading")
ax.grid(True, linestyle='--', alpha=0.5)
ax.legend(loc='upper left')

frame_count = 0

def update(frame):
    global frame_count

    while ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        
        # Parse: "Calibrated Value: 123  |  Raw Value: 456"
        match = re.search(r'Calibrated Value:\s*(-?\d+)\s*\|\s*Raw Value:\s*(-?\d+)', line)
        if match:
            cal_val = int(match.group(1))
            raw_val = int(match.group(2))

            frame_count += 1
            x_data.append(frame_count)
            cal_data.append(cal_val)
            #raw_data.append(raw_val)

            if len(x_data) > MAX_POINTS:
                x_data.pop(0)
                cal_data.pop(0)
                #raw_data.pop(0)

    if x_data:
        line_cal.set_data(x_data, cal_data)
        #line_raw.set_data(x_data, raw_data)

        ax.set_xlim(x_data[0], x_data[-1] + 1)
        
        all_vals = cal_data + raw_data
        min_val, max_val = min(all_vals), max(all_vals)
        margin = max(10, int((max_val - min_val) * 0.1))
        ax.set_ylim(min_val - margin, max_val + margin)

    return line_cal #, line_raw

ani = FuncAnimation(fig, update, interval=20, blit=False, cache_frame_data=False)

plt.tight_layout()
plt.show()

ser.close()