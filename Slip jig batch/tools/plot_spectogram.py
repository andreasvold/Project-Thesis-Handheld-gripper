#!/usr/bin/env python3
"""
Spectrogram (how the frequency content changes over time) of a capture saved by capture.py.

  python plot_spectrogram.py                          newest capture, all sensors
  python plot_spectrogram.py --sensors piezo
  python plot_spectrogram.py --seg-ms 50 --fmax 500   finer time, zoomed frequency
  python plot_spectrogram.py --window 1 4 --save spec.png --no-show
  python plot_spectrogram.py --name mytest            save as tools/plots/spectrogram/mytest.png
  python plot_spectrogram.py --no-save                do not save the plot automatically

After the plot window is closed, the figure is saved automatically to
tools/plots/spectrogram/, using the capture file's name. Use --name to choose
another name, or --no-save to turn saving off.

--seg-ms sets the length of each time slice. Short slices show when things
happen more precisely; long slices show frequencies more precisely.
The time axis starts at the beginning of the analysed window.
The samples are resampled onto an even time grid first (see plot_fft.py).
Needs plot_capture.py in the same folder.
"""
import argparse
import sys

import matplotlib.mlab as mlab
import matplotlib.pyplot as plt
import numpy as np

from plot_capture import newest_capture, parse_capture, show_and_save


def uniform_signal(t, y):
    """Resample y(t) onto an evenly spaced grid. Returns (sample_rate_hz, y_uniform)."""
    n = len(t)
    fs = (n - 1) / (t[-1] - t[0])
    t_uniform = np.linspace(t[0], t[-1], n)
    return fs, np.interp(t_uniform, t, y)


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


def main():
    ap = argparse.ArgumentParser(description="Spectrogram of ESP32-C6 debug captures.")
    ap.add_argument("file", nargs="?", help="capture file (default: newest in captures/)")
    ap.add_argument("--sensors", nargs="+", metavar="NAME", help="sensors to show (default: all)")
    ap.add_argument("--window", nargs=2, type=float, metavar=("T0", "T1"),
                    help="analyse only this time window, in seconds")
    ap.add_argument("--raw", action="store_true", help="use raw counts instead of g / V")
    ap.add_argument("--seg-ms", type=float, default=100.0,
                    help="length of each time slice in ms (default: 100)")
    ap.add_argument("--fmax", type=float, help="upper frequency limit in Hz (default: Nyquist)")
    ap.add_argument("--save", metavar="FILE.png", help="also save the figure to this file")
    ap.add_argument("--no-show", action="store_true", help="do not open a plot window")
    ap.add_argument("--no-save", action="store_true",
                    help="do not save the plot to tools/plots/spectrogram/")
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
        y_uniform = y_uniform - y_uniform.mean()

        # Slice length in samples: a power of two closest to seg_ms
        nfft = 2 ** int(round(np.log2(fs * args.seg_ms / 1000.0)))
        nfft = max(16, min(nfft, len(y_uniform)))

        label = f"{cap.name} {ch}"
        unit = "counts" if args.raw else cap.unit
        print(f"{label}: effective rate {fs:.2f} Hz, slice {nfft} samples "
              f"({1000 * nfft / fs:.1f} ms, resolution {fs / nfft:.2f} Hz)")
        results.append((label, y_uniform, fs, nfft, unit))

    if not results:
        sys.exit("Nothing to plot (check --sensors and --window).")

    n = len(results)
    fig, axes = plt.subplots(n, 1, figsize=(11, 3.4 * n), squeeze=False)
    for ax, (label, y, fs, nfft, unit) in zip(axes[:, 0], results):
        _, freqs, times, im = ax.specgram(
            y, NFFT=nfft, Fs=fs, noverlap=nfft // 2,
            window=mlab.window_hanning, cmap="viridis")

        fmax = args.fmax or fs / 2
        ax.set_ylim(0, fmax)
        ax.set_title(f"{label} spectrogram   (slice {1000 * nfft / fs:.0f} ms, "
                     f"resolution {fs / nfft:.1f} Hz)")
        # Keep the time label in one shared place below all panels. Repeating
        # it on every axis makes it collide with the next panel's title.
        ax.set_ylabel("Frequency (Hz)")
        fig.colorbar(im, ax=ax, label=f"Power (dB re {unit}^2/Hz)")

    fig.supxlabel("Time from window start (s)", y=0.015)
    fig.tight_layout(rect=(0, 0.04, 1, 1), h_pad=2.0)
    show_and_save(fig, "spectrogram", path, name=args.name,
                  show=not args.no_show, auto_save=not args.no_save, save_path=args.save)


if __name__ == "__main__":
    main()