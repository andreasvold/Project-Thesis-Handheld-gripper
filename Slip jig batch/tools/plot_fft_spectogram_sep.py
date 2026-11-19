#!/usr/bin/env python3
"""Generate FFT and spectrogram plots for one sensor capture. use python tools/plot_analysis.py tools/captures/your-capture.txt"""
import argparse
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ANALYSES = (
    ("FFT", HERE / "plot_fft.py"),
    ("Spectrogram", HERE / "plot_spectogram.py"),
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate FFT and spectrogram plots for a sensor capture."
    )
    parser.add_argument("file", help="path to the raw sensor capture file")
    args = parser.parse_args()

    capture = Path(args.file)
    if not capture.is_file():
        parser.error(f"capture file does not exist: {capture}")

    for label, script in ANALYSES:
        print(f"\nGenerating {label} plot...", flush=True)
        result = subprocess.run(
            [sys.executable, str(script), str(capture), "--no-show"],
            check=False,
        )
        if result.returncode:
            return result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main())
