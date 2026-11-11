#!/usr/bin/env python3
"""
Frequency spectrum (FFT) of a capture saved by capture.py.

  python plot_fft.py                           newest capture, all sensors
  python plot_fft.py --sensors accel           accelerometer only
  python plot_fft.py --sensors piezo --fmax 300
  python plot_fft.py --db                      magnitude in dB
  python plot_fft.py --window 1 4              analyse only 1 s to 4 s
  python plot_fft.py captures/capture_x.txt --save fft.png --no-show
  python plot_fft.py --name mytest             save as tools/plots/fft/mytest.png
  python plot_fft.py --no-save                 do not save the plot automatically

After the plot window is closed, the figure is saved automatically to
tools/plots/fft/, using the capture file's name. Use --name to choose another
name, or --no-save to turn saving off.

The samples are not evenly spaced in time, so each signal is first resampled
onto a uniform grid (linear interpolation) at its average rate.
Needs plot_capture.py in the same folder.
"""
import argparse
import sys

import matplotlib.pyplot as plt
import numpy as np

from plot_capture import newest_capture, parse_capture, show_and_save


def uniform_signal(t, y):
    """Resample y(t) onto an evenly spaced grid. Returns (sample_rate_hz, y_uniform)."""
    n = len(t)
    fs = (n - 1) / (t[-1] - t[0])
    t_uniform = np.linspace(t[0], t[-1], n)
    return fs, np.interp(t_uniform, t, y)


def amplitude_spectrum(y, fs):
    """Single-sided amplitude spectrum with a Hann window (amplitude-correct for sine waves)."""
    y = y - y.mean()                          # remove DC
    w = np.hanning(len(y))
    spec = np.fft.rfft(y * w)
    freqs = np.fft.rfftfreq(len(y), d=1.0 / fs)
    amp = 2.0 * np.abs(spec) / w.sum()
    amp[0] /= 2.0                             # DC bin is not doubled
    return freqs, amp


def selected_pairs(caps, raw, window):
    """Yield (cap, channel_name, t, values) for every channel, optionally cut to a time window."""
    for cap in caps:
        t = cap.t
        vals = cap.values(raw)
        if window:
            m = (t >= window[0]) & (t <= window[1])
            t, vals = t[m], vals[m]
        if len(t) < 16:
            print(f"skipping {cap.name}: not enough samples in the time window", file=sys.stderr)
            continue
        for i, ch in enumerate(cap.channels):
            yield cap, ch, t, vals[:, i]


def print_peaks(label, freqs, amp, n=3):
    idx = np.argsort(amp[1:])[::-1][:n] + 1  # skip the DC bin
    peaks = ", ".join(f"{freqs[i]:.2f} Hz (amp {amp[i]:.4g})" for i in idx)
    print(f"  {label:<14} strongest: {peaks}")


def main():
    ap = argparse.ArgumentParser(description="FFT of ESP32-C6 debug captures.")
    ap.add_argument("file", nargs="?", help="capture file (default: newest in captures/)")
    ap.add_argument("--sensors", nargs="+", metavar="NAME", help="sensors to show (default: all)")
    ap.add_argument("--window", nargs=2, type=float, metavar=("T0", "T1"),
                    help="analyse only this time window, in seconds")
    ap.add_argument("--raw", action="store_true", help="use raw counts instead of g / V")
    ap.add_argument("--db", action="store_true", help="plot amplitude in dB")
    ap.add_argument("--fmax", type=float, help="upper frequency limit in Hz (default: Nyquist)")
    ap.add_argument("--save", metavar="FILE.png", help="also save the figure to this file")
    ap.add_argument("--no-show", action="store_true", help="do not open a plot window")
    ap.add_argument("--no-save", action="store_true",
                    help="do not save the plot to tools/plots/fft/")
    ap.add_argument("--name", metavar="NAME",
                    help="name for the saved plot, without .png (default: capture file name)")
    args = ap.parse_args()

    path = args.file or newest_capture()
    print(f"Reading {path}")
    sensors = parse_capture(path)
    if not sensors:
        sys.exit("No #SENSOR blocks found in that file.")

    if args.sensors:
        missing = [s for s in args.sensors if s not in sensors]
        if missing:
            sys.exit(f"Not in this capture: {missing}. Available: {list(sensors)}")
        caps = [sensors[s] for s in args.sensors]
    else:
        caps = list(sensors.values())

    results = []
    for cap, ch, t, y in selected_pairs(caps, args.raw, args.window):
        fs, y_uniform = uniform_signal(t, y)
        freqs, amp = amplitude_spectrum(y_uniform, fs)
        label = f"{cap.name} {ch}"
        unit = "counts" if args.raw else cap.unit
        print(f"{label}: {len(y_uniform)} samples, effective rate {fs:.2f} Hz")
        print_peaks(label, freqs, amp)
        results.append((label, freqs, amp, fs, unit))

    if not results:
        sys.exit("Nothing to plot (check --sensors and --window).")

    n = len(results)
    fig, axes = plt.subplots(n, 1, figsize=(11, 2.8 * n), squeeze=False)
    for ax, (label, freqs, amp, fs, unit) in zip(axes[:, 0], results):
        if args.db:
            y = 20 * np.log10(amp + 1e-12)
            ylabel = f"Amplitude (dB re {unit})"
        else:
            y = amp
            ylabel = f"Amplitude ({unit})"

        fmax = args.fmax or fs / 2
        m = freqs <= fmax
        ax.plot(freqs[m], y[m], lw=0.9)
        ax.set_xlim(0, fmax)
        ax.set_title(f"{label} FFT   (sample rate {fs:.1f} Hz, Nyquist {fs / 2:.1f} Hz)")
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle="--", alpha=0.5)

    fig.tight_layout()
    show_and_save(fig, "fft", path, name=args.name,
                  show=not args.no_show, auto_save=not args.no_save, save_path=args.save)


if __name__ == "__main__":
    main()