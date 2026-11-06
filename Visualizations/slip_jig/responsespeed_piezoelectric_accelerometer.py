#!/usr/bin/env python3
"""
Accelerometer vs. piezo vibration sensor comparison.

Reads the CSV stream from the PlatformIO firmware:
    t_us,ax,ay,az,piezo,piezo_pp
(timestamp in microseconds, raw accelerometer counts, raw 10-bit ADC values)

Usage:  python compare_sensors.py [PORT]      e.g. COM3 or /dev/ttyUSB0
Close the PlatformIO serial monitor first - only one program can use the port.
"""
import sys
import time
import select

import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports
from scipy.signal import butter, lfilter, lfilter_zi

# --- Cross-Platform Non-Blocking Input (for Enter key detection) ---
try:
    import msvcrt
    def is_enter_pressed():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            return ch in (b'\r', b'\n')
        return False
except ImportError:
    import select
    def is_enter_pressed():
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if dr:
            line = sys.stdin.readline()
            return True
        return False

# --- Configuration ---
BAUD_RATE = 250000       # must match Serial.begin() in the firmware
V_REF = 5.0                 # ADC reference voltage (3.3 on 3.3 V boards)
ADC_MAX = 1023.0            # 10-bit ADC
COUNTS_PER_G = 1024.0       # MMA8452Q 12-bit at +/-2 g (use 4096 for MMA8451Q 14-bit)
G_STD = 9.80665             # m/s^2 per g

# --- High-pass filter, applied identically to the piezo and the accelerometer ---
HP_CUTOFF = 100.0           # Hz
HP_ORDER = 2

# --- Trigger thresholds (on the high-passed signals) ---
PIEZO_THRESHOLD_V = 0.02    # Volts
ACC_THRESHOLD_G = 0.05      # g (vector magnitude of X, Y, Z)

TARE_S = 1.0                # baseline recording time
TIMEOUT_S = 300.0           # fallback max duration (5 minutes)
ENV_WINDOW_S = 0.02         # moving-RMS window for the envelope comparison

# --- Plot window ---
PLOT_FRACTION = 0.05        # plot this fraction of the total recording time
PLOT_PRE_FRACTION = 0.2     # portion of that window shown before the first detection

N_FIELDS = 6                # t_us, ax, ay, az, piezo, piezo_pp
WRAP_US = 2.0 ** 32         # micros() is a 32-bit counter


# --- Auto-detect Arduino Port ---
def get_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if any(k in (p.description or "") for k in ["Arduino", "CH340", "USB", "Serial"]):
            return p.device
    return ports[0].device if ports else None


class SerialReader:
    """Reads CSV lines from the port and returns them as numeric rows."""

    def __init__(self, ser):
        self.ser = ser
        self.reset()

    def reset(self):
        self.ser.reset_input_buffer()
        self.buf = b""
        self.synced = False  # the first line after a flush is probably partial: drop it

    def read_rows(self):
        """Return an (N, 6) array with all complete, valid lines received so far."""
        self.buf += self.ser.read(max(self.ser.in_waiting, 1))
        if len(self.buf) > 65536:  # garbage without newlines
            self.buf = b""
        if not self.synced:
            if b"\n" not in self.buf:
                return np.empty((0, N_FIELDS))
            self.buf = self.buf.split(b"\n", 1)[1]
            self.synced = True

        *lines, self.buf = self.buf.split(b"\n")
        rows = []
        for line in lines:
            parts = line.decode("ascii", errors="ignore").strip().split(",")
            if len(parts) != N_FIELDS:
                continue
            try:
                rows.append([float(p) for p in parts])
            except ValueError:  # header line or corrupted line
                continue
        return np.array(rows).reshape(-1, N_FIELDS)


class StreamingHighPass:
    """Butterworth high-pass that keeps its state between batches (multi-channel)."""

    def __init__(self, b, a):
        self.b, self.a, self.zi = b, a, None

    def __call__(self, x):  # x: (N, channels)
        if self.zi is None:
            self.zi = np.outer(lfilter_zi(self.b, self.a), x[0])
        y, self.zi = lfilter(self.b, self.a, x, axis=0, zi=self.zi)
        return y


def seconds_since(t_us, t0_us):
    """Elapsed seconds from the Arduino's micros() timestamps (handles wrap-around)."""
    return ((t_us - t0_us) % WRAP_US) / 1e6


def to_signals(rows):
    """Raw counts -> (accel in g, piezo in V, piezo peak-to-peak in V)."""
    acc = rows[:, 1:4] / COUNTS_PER_G
    piezo = rows[:, 4] * V_REF / ADC_MAX
    piezo_pp = rows[:, 5] * V_REF / ADC_MAX
    return acc, piezo, piezo_pp


def collect(reader, seconds):
    reader.reset()
    chunks = []
    end = time.time() + seconds
    while time.time() < end:
        rows = reader.read_rows()
        if len(rows):
            chunks.append(rows)
    return np.vstack(chunks) if chunks else np.empty((0, N_FIELDS))


def record(reader, hp):
    """Record continuously until the user hits ENTER or the hard timeout is reached."""
    reader.reset()
    chunks, hp_chunks = [], []
    t0, t_acc, t_pz = None, None, None
    start = time.time()

    print("\n--- Live status ---")
    try:
        while time.time() - start < TIMEOUT_S:
            if is_enter_pressed():
                print("\n[USER ACTION] Stop signal (ENTER) received. Finishing recording...")
                break

            rows = reader.read_rows()
            if not len(rows):
                time.sleep(0.001)
                continue

            if t0 is None:
                t0 = rows[0, 0]

            acc, piezo, _ = to_signals(rows)
            y = hp(np.column_stack([acc, piezo]))
            t = seconds_since(rows[:, 0], t0)
            chunks.append(rows)
            hp_chunks.append(y)

            # Check for initial threshold detection (first occurrence only)
            if t_acc is None:
                hit = np.linalg.norm(y[:, :3], axis=1) >= ACC_THRESHOLD_G
                if hit.any():
                    t_acc = t[hit.argmax()]
                    print(f" -> Accelerometer initial detection at t = {t_acc:.4f} s")

            if t_pz is None:
                hit = np.abs(y[:, 3]) >= PIEZO_THRESHOLD_V
                if hit.any():
                    t_pz = t[hit.argmax()]
                    print(f" -> Piezo initial detection at t = {t_pz:.4f} s")

        else:
            print(f"\n[TIMEOUT] Reached max trial length of {TIMEOUT_S:.0f} seconds.")

    except KeyboardInterrupt:
        print("\nTrial aborted by user via Ctrl+C.")

    if not chunks:
        return None
    return np.vstack(chunks), np.vstack(hp_chunks), t_acc, t_pz


def tare_baseline(tare_rows, b, a):
    """Mean levels and high-passed noise RMS measured while the sensors are at rest."""
    acc, piezo, piezo_pp = to_signals(tare_rows)
    y = StreamingHighPass(b, a)(np.column_stack([acc, piezo]))
    acc_noise = np.sqrt(np.mean(np.sum(y[:, :3] ** 2, axis=1)))
    pz_noise = np.sqrt(np.mean(y[:, 3] ** 2))
    return {
        "acc_mean": acc.mean(axis=0),
        "pz_mean": piezo.mean(),
        "pp_mean": piezo_pp.mean(),
        "acc_noise": max(acc_noise, 1.0 / COUNTS_PER_G),
        "pz_noise": max(pz_noise, V_REF / ADC_MAX),
    }


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else get_port()
    if not port:
        sys.exit("[ERROR] No serial port found. Pass it as an argument, e.g. python compare_sensors.py COM3")

    ser = serial.Serial(port, BAUD_RATE, timeout=0.001)
    print(f"Connected to {port} at {BAUD_RATE} baud (V_REF = {V_REF} V).")
    time.sleep(2.0)
    reader = SerialReader(ser)

    try:
        # --- Step 1: Taring ---
        input("Press [ENTER] to perform taring (keep sensors still and untouched)...")
        print(f"Taring (gathering baseline for {TARE_S:.0f} second)...")
        tare_rows = collect(reader, TARE_S)
        if len(tare_rows) < 50:
            sys.exit("[ERROR] Too little data while taring. Check baud rate, wiring, "
                     "and that the serial monitor is closed.")

        tare_t = seconds_since(tare_rows[:, 0], tare_rows[0, 0])
        tare_fs = (len(tare_rows) - 1) / tare_t[-1]
        if HP_CUTOFF >= tare_fs / 2:
            sys.exit(f"[ERROR] HP_CUTOFF ({HP_CUTOFF} Hz) must be below Nyquist ({tare_fs / 2:.0f} Hz).")
        b, a = butter(HP_ORDER, HP_CUTOFF / (tare_fs / 2), btype="highpass")

        base = tare_baseline(tare_rows, b, a)
        print(f"Line rate during tare: {tare_fs:.1f} Hz ({len(tare_rows)} samples)")
        print(f"Tare baseline piezo: {base['pz_mean']:.3f} V, "
              f"accel: X={base['acc_mean'][0]:+.3f} Y={base['acc_mean'][1]:+.3f} "
              f"Z={base['acc_mean'][2]:+.3f} g")
        print(f"Noise after {HP_CUTOFF:.0f} Hz high-pass: piezo {base['pz_noise'] * 1000:.1f} mV RMS, "
              f"accel {base['acc_noise'] * 1000:.1f} mg RMS")
        if PIEZO_THRESHOLD_V < 4 * base["pz_noise"]:
            print("[WARNING] Piezo threshold is below 4x the noise - may trigger falsely.")
        if ACC_THRESHOLD_G < 4 * base["acc_noise"]:
            print("[WARNING] Accelerometer threshold is below 4x the noise - may trigger falsely.\n")

        # --- Step 2: Recording ---
        input("\nPress [ENTER] to start recording the experiment...")
        print(">>> RECORDING STARTED... Press [ENTER] at any time to stop the experiment <<<")
        result = record(reader, StreamingHighPass(b, a))
    finally:
        ser.close()

    if result is None or len(result[0]) < 5:
        sys.exit("[ERROR] Not enough data collected during trial.")
    report_and_plot(*result, base)


def integrate_velocity(acc_ms2, t):
    """Trapezoidal integration of acceleration (m/s^2) to velocity (m/s), per axis."""
    dt = np.diff(t)
    v = np.zeros_like(acc_ms2)
    v[1:] = np.cumsum(0.5 * (acc_ms2[1:] + acc_ms2[:-1]) * dt[:, None], axis=0)
    return v


def report_and_plot(rows, y, t_acc, t_pz, base):
    t = seconds_since(rows[:, 0], rows[0, 0])
    n = len(t)
    true_fs = (n - 1) / t[-1]

    acc, piezo, piezo_pp = to_signals(rows)
    acc_rel = acc - base["acc_mean"]
    acc_mag = np.linalg.norm(y[:, :3], axis=1)
    pz_hp = y[:, 3]

    # Envelopes (moving RMS)
    n_env = max(3, int(ENV_WINDOW_S * true_fs))

    def moving_rms(x):
        return np.sqrt(np.convolve(x ** 2, np.ones(n_env) / n_env, mode="same"))

    env_acc, env_pz = moving_rms(acc_mag), moving_rms(pz_hp)
    snr_acc = env_acc / base["acc_noise"]
    snr_pz = env_pz / base["pz_noise"]
    snr_pp = piezo_pp / max(base["pp_mean"], V_REF / ADC_MAX)
    corr = np.corrcoef(env_acc, env_pz)[0, 1]

    # Average velocity from the accelerometer, X axis only
    v = integrate_velocity(y[:, 0:1] * G_STD, t)   # column 0 = X
    v -= v.mean(axis=0)
    speed = np.abs(v[:, 0])
    avg_speed = speed.mean()
    peak_speed = speed.max()

    # --- Plot window: a fraction of the total recording, starting just before the first detection ---
    total_T = t[-1]
    win_len = PLOT_FRACTION * total_T
    detections = [x for x in (t_acc, t_pz) if x is not None]
    t_ref = min(detections) if detections else 0.0
    t_lo = max(0.0, t_ref - PLOT_PRE_FRACTION * win_len)
    t_hi = t_lo + win_len
    if t_hi > total_T:                      # keep full window width near the end of the recording
        t_hi = total_T
        t_lo = max(0.0, t_hi - win_len)
    show = (t >= t_lo) & (t <= t_hi)
    tp = t[show]

    print("\n--- TRIAL RESULTS ---")
    print(f"Total samples recorded: {n}")
    print(f"Measured sample rate (true FS): {true_fs:.1f} Hz")
    print(f"Recording length: {total_T:.3f} seconds")
    print(f"Plot window: {t_lo:.3f} to {t_hi:.3f} s ({PLOT_FRACTION * 100:.0f}% of recording)")

    print("\n--- INITIAL DETECTION TIMES ---")
    for name, tt, thr in (("Accelerometer", t_acc, f"{ACC_THRESHOLD_G} g"),
                          ("Piezo", t_pz, f"{PIEZO_THRESHOLD_V} V")):
        print(f"{name:14s}: " + (f"{tt:.4f} s (threshold {thr})" if tt is not None
                                  else f"did not detect threshold ({thr})"))
    if t_acc is not None and t_pz is not None:
        d = (t_pz - t_acc) * 1000
        print(f"Piezo detected {abs(d):.1f} ms {'after' if d >= 0 else 'before'} the accelerometer")

    print("\n--- SENSITIVITY ---")
    print(f"Accelerometer: peak {acc_mag.max():.3f} g, peak envelope = {snr_acc.max():.1f}x noise")
    print(f"Piezo:         peak {np.abs(pz_hp).max():.3f} V, peak envelope = {snr_pz.max():.1f}x noise")
    print(f"Piezo p-p (fast sampling): peak {piezo_pp.max():.3f} V = {snr_pp.max():.1f}x baseline")
    print(f"Envelope correlation (accel vs piezo): {corr:.2f}")

    print("\n--- AVERAGE VELOCITY (accelerometer X) ---")
    print(f"Average speed: {avg_speed:.4f} m/s ({avg_speed * 1000:.1f} mm/s)")
    print(f"Peak speed:    {peak_speed:.4f} m/s")

    # --- Plotting (windowed) ---
    fig, axes = plt.subplots(5, 1, figsize=(11, 11), sharex=True)
    ax_acc, ax_raw, ax_hp_acc, ax_hp_pz, ax_snr = axes

    ax_acc.plot(tp, acc_rel[show, 0], linewidth=0.9, label="X")
    ax_acc.plot(tp, acc_rel[show, 1], linewidth=0.9, label="Y")
    ax_acc.plot(tp, acc_rel[show, 2], linewidth=0.9, label="Z")
    ax_acc.set_title("1. Accelerometer X/Y/Z (tare-subtracted)")
    ax_acc.set_ylabel("Accel (g)")
    ax_acc.legend(loc="upper left", ncol=3)

    ax_raw.plot(tp, piezo[show], color="orange", linewidth=1.0)
    ax_raw.axhline(base["pz_mean"], color="blue", linestyle="--", alpha=0.7,
                   label=f"Tare baseline ({base['pz_mean']:.3f} V)")
    ax_raw.set_title("2. Raw vibration sensor (piezo)")
    ax_raw.set_ylabel("Voltage (V)")
    ax_raw.set_ylim(-0.05, V_REF + 0.05)
    ax_raw.legend(loc="upper left")

    ax_hp_acc.plot(tp, acc_mag[show], color="mediumseagreen", linewidth=1.0)
    ax_hp_acc.axhline(ACC_THRESHOLD_G, color="red", linestyle="--", alpha=0.6,
                      label=f"Threshold ({ACC_THRESHOLD_G} g)")
    ax_hp_acc.set_title(f"3. Accelerometer magnitude, {HP_CUTOFF:.0f} Hz high-passed"
                        + (f" - first detected at t = {t_acc:.3f} s" if t_acc is not None else " - no initial detection"))
    ax_hp_acc.set_ylabel("|a| (g)")
    ax_hp_acc.legend(loc="upper left")

    ax_hp_pz.plot(tp, pz_hp[show], color="dodgerblue", linewidth=1.0)
    ax_hp_pz.axhline(0, color="black", linewidth=0.8)
    ax_hp_pz.axhline(PIEZO_THRESHOLD_V, color="red", linestyle="--", alpha=0.6,
                     label=f"Threshold (+/-{PIEZO_THRESHOLD_V} V)")
    ax_hp_pz.axhline(-PIEZO_THRESHOLD_V, color="red", linestyle="--", alpha=0.6)
    ax_hp_pz.set_title(f"4. Piezo, {HP_CUTOFF:.0f} Hz high-passed"
                       + (f" - first detected at t = {t_pz:.3f} s" if t_pz is not None else " - no initial detection"))
    ax_hp_pz.set_ylabel("Filtered (V)")
    ax_hp_pz.legend(loc="upper left")

    floor = 0.1
    ax_snr.plot(tp, np.clip(snr_acc[show], floor, None), color="mediumseagreen", label="Accelerometer envelope")
    ax_snr.plot(tp, np.clip(snr_pz[show], floor, None), color="dodgerblue", label="Piezo envelope")
    ax_snr.plot(tp, np.clip(snr_pp[show], floor, None), color="darkorange", linewidth=0.8, alpha=0.8,
                label="Piezo peak-to-peak (fast sampling)")
    ax_snr.axhline(1.0, color="black", linestyle=":", linewidth=0.8)
    ax_snr.set_yscale("log")
    ax_snr.set_title("5. Sensitivity comparison: signal relative to each sensor's own tare baseline")
    ax_snr.set_ylabel("x above baseline")
    ax_snr.set_xlabel("Time (seconds)")
    ax_snr.legend(loc="upper left")

    # Add vertical lines for initial threshold detections across all subplots
    for ax in axes:
        ax.set_xlim(t_lo, t_hi)
        ax.grid(True, linestyle="--", alpha=0.5)
        if t_acc is not None:
            ax.axvline(t_acc, color="mediumseagreen", linestyle=":", linewidth=1.2, label="Acc Init Detect" if ax == ax_acc else "")
        if t_pz is not None:
            ax.axvline(t_pz, color="dodgerblue", linestyle=":", linewidth=1.2, label="Piezo Init Detect" if ax == ax_acc else "")

    fig.suptitle(f"Average velocity (accelerometer X): {avg_speed:.4f} m/s "
                 f"({avg_speed * 1000:.1f} mm/s)", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()


if __name__ == "__main__":
    main()