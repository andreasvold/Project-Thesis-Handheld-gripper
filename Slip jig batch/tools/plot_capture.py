#!/usr/bin/env python3
"""
Plot a capture saved by capture.py (or a raw dump copied from a terminal).

  python plot_capture.py                          newest capture, all sensors
  python plot_capture.py --sensors piezo          only the piezo
  python plot_capture.py --sensors accel --window 0 2.5
  python plot_capture.py --raw                    raw counts instead of g / V
  python plot_capture.py --stats                  timing and value statistics, no plot
  python plot_capture.py captures/capture_x.txt --save out.png --no-show
  python plot_capture.py --name mytest            save as tools/plots/capture/mytest.png
  python plot_capture.py --no-save                do not save the plot automatically

After the plot window is closed, the figure is saved automatically to
tools/plots/capture/, using the capture file's name (capture_x.png for
capture_x.txt). Use --name to choose another name, or --no-save to turn
saving off.
"""
import argparse
import glob
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(HERE, "captures")
PLOTS_DIR = os.path.join(HERE, "plots")


class SensorCapture:
    """One #SENSOR ... #END block of a capture file."""

    def __init__(self, name, meta, columns, data):
        self.name = name
        self.meta = meta              # key=value pairs from the #SENSOR line
        self.columns = columns        # e.g. ["t_us", "ax", "ay", "az"]
        self.data = data              # float array, shape (N, len(columns))

    @property
    def t(self):
        """Seconds since the start of the capture."""
        return self.data[:, 0] / 1e6

    @property
    def channels(self):
        return self.columns[1:]

    @property
    def unit(self):
        return str(self.meta.get("unit", "counts"))

    def values(self, raw=False):
        """Shape (N, channels). Physical units (g, V) unless raw=True."""
        v = self.data[:, 1:]
        if raw:
            return v
        return v * float(self.meta.get("scale", 1.0))


def _parse_value(text):
    for convert in (int, float):
        try:
            return convert(text)
        except ValueError:
            pass
    return text


def _make_capture(name, meta, columns, rows):
    if not columns or not rows:
        print(f"warning: sensor '{name}' has no data", file=sys.stderr)
        return None
    good = [r for r in rows if len(r) == len(columns)]
    return SensorCapture(name, meta, columns, np.array(good, dtype=float))


def parse_capture(path):
    """Return {sensor_name: SensorCapture} in the order they appear in the file."""
    sensors = {}
    name, meta, columns, rows = None, {}, None, []
    skipped = 0

    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            if line.startswith("#SENSOR "):
                tokens = line.split()
                name = tokens[1]
                meta = {}
                for tok in tokens[2:]:
                    if "=" in tok:
                        key, value = tok.split("=", 1)
                        meta[key] = _parse_value(value)
                columns, rows = None, []

            elif line.startswith("#END ") and name is not None:
                cap = _make_capture(name, meta, columns, rows)
                if cap is not None:
                    sensors[name] = cap
                name = None

            elif name is not None:
                if columns is None:
                    columns = line.split(",")
                else:
                    try:
                        rows.append([float(x) for x in line.split(",")])
                    except ValueError:
                        skipped += 1

    if skipped:
        print(f"warning: skipped {skipped} malformed line(s)", file=sys.stderr)
    return sensors


def newest_capture():
    files = glob.glob(os.path.join(CAPTURE_DIR, "*.txt"))
    if not files:
        sys.exit(f"No captures found in {CAPTURE_DIR}. Run capture.py first.")
    return max(files, key=os.path.getmtime)


# ---------------------------------------------------------------------
# Saving plots (shared with plot_fft.py and plot_spectrogram.py)
# ---------------------------------------------------------------------
def make_plot_path(kind, capture_path, name=None):
    """
    Path for a saved plot. By default it uses the capture file's name, so
    captures/capture_x.txt -> plots/fft/capture_x.png. Pass name to choose a
    different name. Existing files are never overwritten: _2, _3, ... is added.
    """
    folder = os.path.join(PLOTS_DIR, kind)
    os.makedirs(folder, exist_ok=True)
    if name:
        base = os.path.basename(name)
    else:
        base = os.path.splitext(os.path.basename(capture_path))[0]
    if base.lower().endswith(".png"):
        base = base[:-4]
    path = os.path.join(folder, base + ".png")
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{n}.png")
        n += 1
    return path


def show_and_save(fig, kind, capture_path, name=None,
                  show=True, auto_save=True, save_path=None):
    """Show the figure (blocks until the window is closed), then save it."""
    if show:
        plt.show()
    if auto_save:
        path = make_plot_path(kind, capture_path, name)
        fig.savefig(path, dpi=150)
        print(f"Saved plot to {path}")
    if save_path:
        fig.savefig(save_path, dpi=150)
        print(f"Saved figure to {save_path}")


# ---------------------------------------------------------------------
# Statistics and plotting
# ---------------------------------------------------------------------
def print_stats(cap, raw):
    t_us = cap.data[:, 0]
    n = len(t_us)
    print(f"\n== {cap.name} ==")
    print(f"  samples                {n}   (device reported {cap.meta.get('samples', '?')})")
    print(f"  missed slots           {cap.meta.get('missed', '?')}   (loop too slow for the rate)")
    print(f"  overwritten by sensor  {cap.meta.get('overwritten', '?')}   (sensor outran our reads)")
    print(f"  nominal rate           {cap.meta.get('rate_hz', '?')} Hz")
    if n >= 2 and t_us[-1] > t_us[0]:
        duration = (t_us[-1] - t_us[0]) / 1e6
        dt = np.diff(t_us)
        print(f"  duration               {duration:.3f} s")
        print(f"  measured rate          {(n - 1) / duration:.2f} Hz")
        print(f"  interval [us]          min {dt.min():.0f}   mean {dt.mean():.1f}   "
              f"max {dt.max():.0f}   std {dt.std():.1f}")

    unit = "counts" if raw else cap.unit
    values = cap.values(raw)
    for i, ch in enumerate(cap.channels):
        v = values[:, i]
        print(f"  {ch:<6} min {v.min():12.4f}  max {v.max():12.4f}  "
              f"mean {v.mean():12.4f}  std {v.std():10.4f}  [{unit}]")


def plot_captures(caps, capture_path, window=None, raw=False,
                  save_path=None, show=True, auto_save=True, name=None):
    fig, axes = plt.subplots(len(caps), 1, figsize=(11, 3.4 * len(caps)), squeeze=False)

    for ax, cap in zip(axes[:, 0], caps):
        t = cap.t
        y = cap.values(raw)
        mask = np.ones(len(t), dtype=bool)
        if window:
            mask = (t >= window[0]) & (t <= window[1])

        for i, ch in enumerate(cap.channels):
            ax.plot(t[mask], y[mask, i], lw=0.9, label=ch)

        rate = cap.meta.get("rate_hz", "?")
        ax.set_title(f"{cap.name}  (nominal {rate} Hz, {len(t)} samples)")
        ax.set_xlabel("time since capture start (s)")
        ax.set_ylabel("counts" if raw else cap.unit)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper right", ncol=min(3, len(cap.channels)))

    fig.tight_layout()
    show_and_save(fig, "capture", capture_path, name=name,
                  show=show, auto_save=auto_save, save_path=save_path)


def main():
    ap = argparse.ArgumentParser(description="Plot ESP32-C6 debug captures.")
    ap.add_argument("file", nargs="?", help="capture file (default: newest in captures/)")
    ap.add_argument("--sensors", nargs="+", metavar="NAME",
                    help="sensors to show, e.g. accel piezo (default: all)")
    ap.add_argument("--window", nargs=2, type=float, metavar=("T0", "T1"),
                    help="time window in seconds")
    ap.add_argument("--raw", action="store_true", help="plot raw counts instead of g / V")
    ap.add_argument("--stats", action="store_true", help="print statistics, no plot")
    ap.add_argument("--save", metavar="FILE.png", help="also save the figure to this file")
    ap.add_argument("--no-show", action="store_true", help="do not open a plot window")
    ap.add_argument("--no-save", action="store_true",
                    help="do not save the plot to tools/plots/capture/")
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

    if args.stats:
        for cap in caps:
            print_stats(cap, args.raw)
        return

    plot_captures(caps, path, window=args.window, raw=args.raw,
                  save_path=args.save, show=not args.no_show,
                  auto_save=not args.no_save, name=args.name)


if __name__ == "__main__":
    main()