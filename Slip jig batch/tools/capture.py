#!/usr/bin/env python3
"""
Trigger a debug capture on the ESP32-C6 and save the dump to tools/captures/.

  python capture.py                 auto-detect the port
  python capture.py COM9            Windows
  python capture.py /dev/ttyACM0    Linux
  python capture.py --status        print device status instead of capturing

Close the PlatformIO serial monitor first (only one program can open the port).
Then plot with:  python plot_capture.py
"""
import argparse
import os
import sys
import time
from datetime import datetime

import serial
import serial.tools.list_ports

BAUD_RATE = 115200
HERE = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(HERE, "captures")
PORT_KEYWORDS = ("usb", "jtag", "serial", "cp210", "ch340", "arduino", "espressif")


def find_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if any(k in (p.description or "").lower() for k in PORT_KEYWORDS):
            return p.device
    return ports[0].device if ports else None


def main():
    ap = argparse.ArgumentParser(description="Capture ESP32-C6 sensor data to a file.")
    ap.add_argument("port", nargs="?", help="serial port (default: auto-detect)")
    ap.add_argument("--baud", type=int, default=BAUD_RATE)
    ap.add_argument("--timeout", type=float, default=180.0,
                    help="max seconds to wait for the device to finish")
    ap.add_argument("--status", action="store_true", help="print device status instead")
    args = ap.parse_args()

    port = args.port or find_port()
    if not port:
        sys.exit("No serial port found. Pass one explicitly, e.g. python capture.py COM9")

    command = "status" if args.status else "capture"
    end_marker = "#STATUS_END" if args.status else "#CAPTURE_END"

    print(f"Opening {port} @ {args.baud} baud ...")
    lines = []
    finished = False
    with serial.Serial(port, args.baud, timeout=0.5) as ser:
        time.sleep(1.5)                       # some boards reset when the port opens
        ser.reset_input_buffer()
        ser.write(f"{command}\n".encode())
        print(f"Sent '{command}', waiting for the device ...")

        deadline = time.time() + args.timeout
        while time.time() < deadline:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            lines.append(line)
            print(line)
            if line.startswith(end_marker):
                finished = True
                break

    if not finished:
        sys.exit("Timed out before the device finished. Check the port and that the firmware is flashed.")
    if args.status:
        return

    os.makedirs(CAPTURE_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(CAPTURE_DIR, f"capture_{stamp}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved {out_path}")
    print(f'Plot with:  python plot_capture.py "{out_path}"')


if __name__ == "__main__":
    main()