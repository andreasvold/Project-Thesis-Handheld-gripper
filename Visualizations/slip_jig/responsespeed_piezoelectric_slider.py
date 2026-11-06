import sys
import time
import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports
from scipy.signal import butter, lfilter, lfilter_zi

# --- Configuration ---
BAUD_RATE = 250000
V_REF = 5.0

# --- High-pass filter settings for the Piezo sensor ---
HP_CUTOFF = 100.0  
HP_ORDER = 2
THRESHOLD_VOLTS = 0.05  # Slip/vibration threshold that triggers trial end (Volts)

# Filter coefficients
b, a = butter(HP_ORDER, HP_CUTOFF / (2500.0 / 2), btype="highpass")


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
print(f"Connected to {port} at {BAUD_RATE} baud (V_REF = {V_REF}V).")

# --- Step 1: Taring Trigger ---
input("Press [ENTER] to perform taring (keep slider still)...")

# Flush any old data lingering in the serial buffer
ser.reset_input_buffer()

print("Taring potentiometer (gathering baseline for 1 second)...")
tare_samples = []
tare_start_time = time.time()

while time.time() - tare_start_time < 1.0:
    if ser.in_waiting:
        line_str = ser.readline().decode("ascii", errors="ignore").strip()
        if "," in line_str:
            parts = line_str.split(",")
            if len(parts) >= 2:
                try:
                    s_val = float(parts[0])
                    s_volt = (s_val / 1023.0) * V_REF
                    tare_samples.append(s_volt)
                except ValueError:
                    continue

if len(tare_samples) > 0:
    tare_voltage = np.mean(tare_samples)
else:
    tare_voltage = 0.0
    print("[WARNING] No valid tare samples collected, defaulting tare baseline to 0.0V.")

print(f"Tare Baseline Potentiometer Value: {tare_voltage:.3f}V ({len(tare_samples)} samples)\n")

# --- Step 2: Experiment Recording Trigger ---
input("Press [ENTER] to start recording the experiment...")

ser.reset_input_buffer()
print(">>> RECORDING STARTED... Perform action now (Waiting for threshold breach) <<<")

# --- Collect Data Until Threshold is Reached ---
slider_record = []
raw_piezo_record = []
hp_piezo_record = []

zi = None
threshold_met = False
t_recording_start = time.time()

try:
    while not threshold_met:
        while ser.in_waiting:
            line_str = ser.readline().decode("ascii", errors="ignore").strip()
            if "," in line_str:
                parts = line_str.split(",")
                if len(parts) >= 2:
                    try:
                        s_val = float(parts[0])
                        p_val = float(parts[1])

                        s_volt = (s_val / 1023.0) * V_REF
                        p_volt = (p_val / 1023.0) * V_REF

                        slider_record.append(s_volt)
                        raw_piezo_record.append(p_volt)

                        # Apply filter sequentially
                        if zi is None:
                            zi = lfilter_zi(b, a) * p_volt
                        
                        filtered_val, zi = lfilter(b, a, [p_volt], zi=zi)
                        f_val = filtered_val[0]
                        hp_piezo_record.append(f_val)

                        # Check if threshold is breached (Trigger to end trial)
                        if abs(f_val) >= THRESHOLD_VOLTS:
                            threshold_met = True
                            break
                    except ValueError:
                        continue
        if threshold_met:
            break
        
        # Safety timeout check (e.g., abort if nothing happens after 30 seconds)
        if time.time() - t_recording_start > 30.0:
            print("\n[TIMEOUT] No threshold breach detected within 30 seconds.")
            break
except KeyboardInterrupt:
    print("\nTrial aborted by user.")
finally:
    ser.close()

if len(slider_record) < 5:
    print("[ERROR] Not enough data collected during trial.")
    raise SystemExit(1)

# --- Calculate True Metrics based on Real Elapsed Time ---
slider_arr = np.array(slider_record)
raw_piezo_arr = np.array(raw_piezo_record)
hp_piezo_arr = np.array(hp_piezo_record)

total_samples = len(slider_arr)
actual_duration = time.time() - t_recording_start  
true_fs = total_samples / actual_duration           

time_axis = np.arange(total_samples) / true_fs

slider_start = slider_arr[0]
slider_end = slider_arr[-1]
slider_delta = slider_end - slider_start
response_time = time_axis[-1]  

# Calculate displacement from the pre-experiment tare average
pot_displacement_from_tare = slider_end - tare_voltage

# --- Calculate Potentiometer Speed ---
# Average speed: Net voltage displacement from start/tare divided by response time (V/s)
avg_speed_from_start = abs(slider_delta) / response_time if response_time > 0 else 0.0
avg_speed_from_tare = abs(pot_displacement_from_tare) / response_time if response_time > 0 else 0.0

# Instantaneous / Peak speed: Max rate of change between adjacent samples
dt = 1.0 / true_fs
if total_samples > 1:
    instantaneous_speeds = np.abs(np.diff(slider_arr)) / dt
    peak_speed = np.max(instantaneous_speeds)
else:
    peak_speed = 0.0

print("\n--- TRIAL RESULTS ---")
print(f"Total samples recorded: {total_samples}")
print(f"Measured Sample Rate (True FS): {true_fs:.1f} Hz")
print(f"Response Time (to threshold): {response_time:.3f} seconds")
print(f"Tare Baseline Potentiometer Value: {tare_voltage:.3f}V")
print(f"Potentiometer Value at Vibration Trigger: {slider_end:.3f}V")
print(f"Displacement from Tare Baseline (Trigger - Tare): {pot_displacement_from_tare:+.3f}V")
print(f"Slider Change (Start to Trigger): {slider_start:.3f}V -> {slider_end:.3f}V (Δ = {slider_delta:+.3f}V)")
print(f"\n--- POTENTIOMETER SPEED METRICS ---")
print(f"Average Speed (from Tare to Trigger): {avg_speed_from_tare:.3f} V/s")
print(f"Average Speed (Start to Trigger): {avg_speed_from_start:.3f} V/s")
print(f"Peak Instantaneous Speed: {peak_speed:.3f} V/s")

# --- Plotting Final Results ---
fig, (ax_slider, ax_raw_piezo, ax_hp_piezo) = plt.subplots(3, 1, figsize=(10, 7), sharex=True)

# 1. Slider Plot
ax_slider.plot(time_axis, slider_arr, color="mediumseagreen", linewidth=1.2)
ax_slider.set_title(f"1. Slider Potentiometer Position (Avg Speed: {avg_speed_from_tare:.2f} V/s, Peak: {peak_speed:.2f} V/s)")
ax_slider.set_ylabel("Voltage (V)")
ax_slider.set_ylim(-0.05, V_REF + 0.05)
ax_slider.grid(True, linestyle="--", alpha=0.5)
ax_slider.axhline(tare_voltage, color="blue", linestyle="--", alpha=0.7, label=f"Tare Baseline ({tare_voltage:.3f}V)")
ax_slider.axhline(slider_end, color="black", linestyle=":", alpha=0.7, label="Trigger Point")
ax_slider.legend(loc="upper left")

# 2. Raw Piezo Plot
ax_raw_piezo.plot(time_axis, raw_piezo_arr, color="orange", linewidth=1.0)
ax_raw_piezo.set_title("2. Raw Vibration Sensor (Piezo)")
ax_raw_piezo.set_ylabel("Voltage (V)")
ax_raw_piezo.set_ylim(-0.05, V_REF + 0.05)
ax_raw_piezo.grid(True, linestyle="--", alpha=0.5)

# 3. High-Passed Piezo Plot with threshold & trigger point
ax_hp_piezo.plot(time_axis, hp_piezo_arr, color="dodgerblue", linewidth=1.0)
ax_hp_piezo.set_title(f"3. High-Passed Vibration — Triggered at t = {response_time:.3f}s")
ax_hp_piezo.set_ylabel("Filtered (V)")
ax_hp_piezo.set_xlabel("Time (seconds)")
ax_hp_piezo.grid(True, linestyle="--", alpha=0.5)
ax_hp_piezo.axhline(0, color="black", linewidth=0.8, linestyle="-")
ax_hp_piezo.axhline(THRESHOLD_VOLTS, color="red", linestyle="--", alpha=0.6, label=f"Threshold (+/-{THRESHOLD_VOLTS}V)")
ax_hp_piezo.axhline(-THRESHOLD_VOLTS, color="red", linestyle="--", alpha=0.6)

ax_hp_piezo.scatter(time_axis[-1], hp_piezo_arr[-1], color="red", s=70, zorder=5, label="Threshold Breached")
ax_hp_piezo.legend(loc="upper left")

plt.tight_layout()
plt.show()