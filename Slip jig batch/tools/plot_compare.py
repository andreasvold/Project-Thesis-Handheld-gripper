#!/usr/bin/env python3
"""
Compare two captures side by side in one figure.

  python plot_compare.py                                   choose files and plot type from menus
  python plot_compare.py a.txt b.txt --mode capture        signals over time (default plot type)
  python plot_compare.py a.txt b.txt --mode fft            frequency spectrum (add --db for dB)
  python plot_compare.py a.txt b.txt --mode spectrogram    frequency content over time
  python plot_compare.py a.txt b.txt --sensors accel --window 0 2
  python plot_compare.py a.txt b.txt --mode fft --fmax 300
  python plot_compare.py a.txt b.txt --mode spectrogram --seg-ms 50
  python plot_compare.py a.txt b.txt --name run1_vs_run2 --no-show

Left column = first file, right column = second file.
Capture and fft plots have one row per sensor. Spectrogram plots have one row
per channel, because each spectrogram shows a single channel.
Plots in the same row share a value axis, so they compare directly.
Each time axis runs from the start of its capture to its last sample (or to
the --window limits).

After the window is closed, the figure is saved to tools/plots/compare/<mode>/.
Needs plot_capture.py in the same folder.
"""
import argparse
import glob
import os
import sys

import matplotlib.mlab as mlab
import matplotlib.pyplot as plt
import numpy as np

from plot_capture import CAPTURE_DIR, parse_capture, show_and_save

MODE_MENU = {"1": "capture", "2": "fft", "3": "spectrogram"}


# ---------------------------------------------------------------------
# Choosing files and plot type
# ---------------------------------------------------------------------
def list_captures():
    return sorted(glob.glob(os.path.join(CAPTURE_DIR, "*.txt")), key=os.path.getmtime)


def check_exists(path):
    if os.path.isfile(path):
        return
    found = [os.path.basename(p) for p in list_captures()]
    listing = ", ".join(found) if found else "none"
    sys.exit(f"File not found: {path}\nCaptures in {CAPTURE_DIR}: {listing}")


def choose_two():
    """Show a numbered list of captures and ask the user to pick two."""
    files = list_captures()
    if len(files) < 2:
        sys.exit(f"Need at least two captures in {CAPTURE_DIR}. Found {len(files)}.")

    print("Captures (newest last):")
    for i, f in enumerate(files, 1):
        print(f"  {i:2d}. {os.path.basename(f)}")

    while True:
        answer = input("Enter the numbers of two captures, e.g. 1 3: ").replace(",", " ").split()
        valid = (len(answer) == 2
                 and all(a.isdigit() and 1 <= int(a) <= len(files) for a in answer)
                 and answer[0] != answer[1])
        if valid:
            return [files[int(answer[0]) - 1], files[int(answer[1]) - 1]]
        print(f"Please enter two different numbers between 1 and {len(files)}.")


def choose_mode():
    print("Plot type:  1) capture (signals over time)   2) fft (spectrum)   3) spectrogram")
    while True:
        answer = input("Choose 1, 2 or 3 [1]: ").strip() or "1"
        if answer in MODE_MENU:
            return MODE_MENU[answer]
        print("Please enter 1, 2 or 3.")


# ---------------------------------------------------------------------
# Signal processing
# ---------------------------------------------------------------------
def uniform_signal(t, y):
    """Resample y(t) onto an evenly spaced grid. Returns (sample_rate_hz, y_uniform)."""
    n = len(t)
    fs = (n - 1) / (t[-1] - t[0])
    t_uniform = np.linspace(t[0], t[-1], n)
    return fs, np.interp(t_uniform, t, y)


def amplitude_spectrum(y, fs):
    """Single-sided amplitude spectrum with a Hann window."""
    y = y - y.mean()
    w = np.hanning(len(y))
    spec = np.fft.rfft(y * w)
    freqs = np.fft.rfftfreq(len(y), d=1.0 / fs)
    amp = 2.0 * np.abs(spec) / w.sum()
    amp[0] /= 2.0
    return freqs, amp


def window_mask(t, window):
    if window:
        return (t >= window[0]) & (t <= window[1])
    return np.ones(len(t), dtype=bool)


def placeholder(ax, sensor):
    ax.text(0.5, 0.5, f"'{sensor}' is not in this capture",
            ha="center", va="center", transform=ax.transAxes, color="gray")
    ax.set_xticks([])
    ax.set_yticks([])


# ---------------------------------------------------------------------
# Drawing one cell (one capture, one row)
# ---------------------------------------------------------------------
def draw_capture(ax, cap, channels, window, raw):
    t = cap.t
    y = cap.values(raw)
    mask = window_mask(t, window)
    for i in channels:
        ax.plot(t[mask], y[mask, i], lw=0.9, label=cap.channels[i])
    if mask.any():
        ax.set_xlim(t[mask][0], t[mask][-1])
    ax.set_xlabel("time since capture start (s)")
    ax.legend(loc="upper right", ncol=min(3, len(channels)), fontsize=8)


def draw_fft(ax, cap, channels, window, raw, fmax, db):
    t = cap.t
    y_all = cap.values(raw)
    mask = window_mask(t, window)
    t, y_all = t[mask], y_all[mask]
    if len(t) < 16:
        ax.text(0.5, 0.5, "not enough samples in window", ha="center", va="center",
                transform=ax.transAxes, color="gray")
        return

    fs = None
    for i in channels:
        fs, y_u = uniform_signal(t, y_all[:, i])
        freqs, amp = amplitude_spectrum(y_u, fs)
        val = 20 * np.log10(amp + 1e-12) if db else amp
        top = fmax or fs / 2
        m = freqs <= top
        ax.plot(freqs[m], val[m], lw=0.9, label=cap.channels[i])

    ax.set_xlim(0, fmax or fs / 2)
    ax.set_xlabel("frequency (Hz)")
    ax.legend(loc="upper right", ncol=min(3, len(channels)), fontsize=8)


def draw_spectrogram(ax, cap, channel, window, raw, fmax, seg_ms):
    t = cap.t
    y_all = cap.values(raw)
    mask = window_mask(t, window)
    t, y = t[mask], y_all[mask, channel]
    if len(t) < 16:
        ax.text(0.5, 0.5, "not enough samples in window", ha="center", va="center",
                transform=ax.transAxes, color="gray")
        return None

    fs, y_u = uniform_signal(t, y)
    y_u = y_u - y_u.mean()
    nfft = 2 ** int(round(np.log2(fs * seg_ms / 1000.0)))
    nfft = max(16, min(nfft, len(y_u)))

    _, freqs, times, im = ax.specgram(
        y_u, NFFT=nfft, Fs=fs, noverlap=nfft // 2,
        window=mlab.window_hanning, cmap="viridis")
    ax.set_ylim(0, fmax or fs / 2)
    ax.set_xlabel("time (s)")
    return im


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Compare two ESP32-C6 captures side by side.")
    ap.add_argument("files", nargs="*", help="two capture files (default: choose from a list)")
    ap.add_argument("--mode", choices=["capture", "fft", "spectrogram"],
                    help="plot type (default: asked in a menu)")
    ap.add_argument("--sensors", nargs="+", metavar="NAME", help="sensors to compare (default: all)")
    ap.add_argument("--window", nargs=2, type=float, metavar=("T0", "T1"),
                    help="time window in seconds, applied to both")
    ap.add_argument("--raw", action="store_true", help="use raw counts instead of g / V")
    ap.add_argument("--db", action="store_true", help="fft mode: show amplitude in dB")
    ap.add_argument("--fmax", type=float, help="fft and spectrogram: upper frequency limit in Hz")
    ap.add_argument("--seg-ms", type=float, default=100.0,
                    help="spectrogram mode: time slice length in ms (default: 100)")
    ap.add_argument("--save", metavar="FILE.png", help="also save the figure to this file")
    ap.add_argument("--no-show", action="store_true", help="do not open a plot window")
    ap.add_argument("--no-save", action="store_true",
                    help="do not save the plot to tools/plots/compare/<mode>/")
    ap.add_argument("--name", metavar="NAME",
                    help="name for the saved plot, without .png (default: first_vs_second)")
    args = ap.parse_args()

    # ---- choose the files ----
    if len(args.files) == 0:
        paths = choose_two()
    elif len(args.files) == 2:
        paths = args.files
    else:
        sys.exit("Give exactly two capture files, or none to choose from a list.")

    for p in paths:
        check_exists(p)

    mode = args.mode or choose_mode()

    labels = [os.path.splitext(os.path.basename(p))[0] for p in paths]
    caps = [parse_capture(p) for p in paths]
    for p, c in zip(paths, caps):
        if not c:
            sys.exit(f"No #SENSOR blocks found in {p}")

    # ---- which sensors ----
    names = list(caps[0]) + [n for n in caps[1] if n not in caps[0]]
    if args.sensors:
        unknown = [s for s in args.sensors if s not in names]
        if unknown:
            sys.exit(f"Not in either capture: {unknown}. Available: {names}")
        names = [n for n in names if n in args.sensors]

    for label, c in zip(labels, caps):
        print(f"{label}: sensors {list(c)}")

    # ---- rows: one per sensor, or one per channel for spectrograms ----
    if mode == "spectrogram":
        rows = []
        for name in names:
            src = next(c[name] for c in caps if name in c)
            for i in range(len(src.channels)):
                rows.append((name, i))
    else:
        rows = [(name, None) for name in names]

    n_rows = len(rows)
    fig, axes = plt.subplots(n_rows, 2, figsize=(15, 3.4 * n_rows), squeeze=False,
                             sharey="row")

    for r, (name, channel) in enumerate(rows):
        row_axes = axes[r, :]
        ims = []
        unit = "counts" if args.raw else next(c[name].unit for c in caps if name in c)

        for col in range(2):
            ax = row_axes[col]
            cap = caps[col].get(name)
            head = f"{labels[col]}  |  {name}"

            if cap is None:
                placeholder(ax, name)
                ax.set_title(head)
                continue

            if mode == "capture":
                channels = list(range(len(cap.channels)))
                draw_capture(ax, cap, channels, args.window, args.raw)
                rate = cap.meta.get("rate_hz", "?")
                ax.set_title(f"{head}  (nominal {rate} Hz, {len(cap.t)} samples)")
                ax.set_ylabel(unit)

            elif mode == "fft":
                channels = list(range(len(cap.channels)))
                draw_fft(ax, cap, channels, args.window, args.raw, args.fmax, args.db)
                ax.set_title(f"{head}  (spectrum)")
                ax.set_ylabel(f"amplitude ({'dB' if args.db else unit})")

            else:  # spectrogram
                if channel >= len(cap.channels):
                    placeholder(ax, name)
                    ax.set_title(head)
                    continue
                im = draw_spectrogram(ax, cap, channel, args.window, args.raw,
                                      args.fmax, args.seg_ms)
                if im is not None:
                    ims.append(im)
                ax.set_title(f"{head}  {cap.channels[channel]}  (slice {args.seg_ms:g} ms)")
                ax.set_ylabel("frequency (Hz)")

            ax.grid(True, linestyle="--", alpha=0.5)

        # Spectrograms in the same row share one colour scale
        if mode == "spectrogram" and ims:
            lo = min(im.get_clim()[0] for im in ims)
            hi = max(im.get_clim()[1] for im in ims)
            for im in ims:
                im.set_clim(lo, hi)
            fig.colorbar(ims[0], ax=list(row_axes), label="power (dB)")

    fig.tight_layout()
    show_and_save(fig, os.path.join("compare", mode), paths[0],
                  name=args.name or f"{labels[0]}_vs_{labels[1]}",
                  show=not args.no_show, auto_save=not args.no_save, save_path=args.save)


if __name__ == "__main__":
    main()