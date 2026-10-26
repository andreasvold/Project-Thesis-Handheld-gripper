
import time

import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports

BAUD_RATE = 115200
RECORD_SECONDS = 3.0
V_REF = 5.0
MAX_FREQ = 500


def get_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if any(k in p.description for k in
               ["Arduino", "CH340", "USB", "Serial"]):
            return p.device
    return ports[0].device if ports else None


port = get_port()
if not port:
    raise RuntimeError("No serial port found.")

ser = serial.Serial(port, BAUD_RATE, timeout=0.02)
time.sleep(2)  # Allow Arduino to reset
print(f"Connected to {port} at {BAUD_RATE} baud.")


try:
    while True:
        input("\nPress ENTER to record for 3 seconds (Ctrl+C to quit)...")

        # Clear old serial data before recording
        ser.reset_input_buffer()
        samples = []
        start = time.perf_counter()

        print("Recording...")
        while time.perf_counter() - start < RECORD_SECONDS:
            line = ser.readline().decode(
                "ascii", errors="ignore"
            ).strip()

            if not line:
                continue

            try:
                raw = float(line.split(",")[0])
                if 0 <= raw <= 1023:
                    samples.append(raw / 1023.0 * V_REF)
            except ValueError:
                continue

        elapsed = time.perf_counter() - start
        samples = np.asarray(samples, dtype=float)

        if len(samples) < 10:
            print(f"Too few samples received: {len(samples)}")
            continue

        # Estimate sample rate and remove DC offset
        fs = len(samples) / elapsed
        signal = samples - np.mean(samples)

        # Compute FFT with a Hann window
        window = np.hanning(len(signal))
        spectrum = np.fft.rfft(signal * window)
        frequencies = np.fft.rfftfreq(len(signal), d=1.0 / fs)

        amplitude = 2 * np.abs(spectrum) / np.sum(window)
        amplitude[0] /= 2

        if len(signal) % 2 == 0:
            amplitude[-1] /= 2

        # Select 0–500 Hz
        mask = frequencies <= MAX_FREQ
        freq_plot = frequencies[mask]
        amp_plot = amplitude[mask]

        # Approximate integral of amplitude spectrum
        s_fft = np.trapezoid(amp_plot, freq_plot)

        print(f"Recording complete: {len(samples)} samples")
        print(f"Estimated sample rate: {fs:.1f} Hz")
        print(f"Frequency resolution: {fs / len(samples):.2f} Hz")
        print(f"S(FFT), 0–{MAX_FREQ} Hz: {s_fft:.6g} V·Hz")

        # Plot signal and spectrum
        t = np.arange(len(signal)) / fs
        fig, axes = plt.subplots(2, 1, figsize=(10, 7))

        axes[0].plot(t, signal, linewidth=0.8)
        axes[0].set_title("Recorded Signal")
        axes[0].set_xlabel("Time (s)")
        axes[0].set_ylabel("Voltage (V, DC removed)")
        axes[0].grid(True, alpha=0.3)

        axes[1].plot(freq_plot, amp_plot, linewidth=0.9)
        axes[1].set_title("FFT Amplitude Spectrum")
        axes[1].set_xlabel("Frequency (Hz)")
        axes[1].set_ylabel("Amplitude (V peak)")
        axes[1].set_xlim(0, MAX_FREQ)
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()
        plt.close(fig)

except KeyboardInterrupt:
    print("\nExiting.")

finally:
    ser.close()
