#!/usr/bin/env python3
"""
Interactive debug capture for the ESP32-C6.

  python capture.py                 auto-detect the port
  python capture.py COM9            Windows
  python capture.py /dev/ttyACM0    Linux
  python capture.py --status        print device status instead

Flow:
  1. The board arms and waits. Press Enter to START recording.
  2. Recording runs. Press Enter to STOP early. If you don't, it stops by
     itself when the buffers are full or the timeout is reached.
  3. The board sends the data, and this script saves it to tools/captures/.

Ctrl+C while armed cancels. Ctrl+C while recording stops and saves.
Close the PlatformIO serial monitor first (only one program can open the port).
"""
import argparse
import os
import sys
import threading
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


def now_str():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def enter_watcher():
    """Return an Event that is set when Enter is pressed. Waits in a background thread."""
    event = threading.Event()

    def wait():
        try:
            input()
        except EOFError:
            pass
        event.set()

    threading.Thread(target=wait, daemon=True).start()
    return event


def main():
    ap = argparse.ArgumentParser(description="Interactive debug capture for the ESP32-C6.")
    ap.add_argument("port", nargs="?", help="serial port (default: auto-detect)")
    ap.add_argument("--baud", type=int, default=BAUD_RATE)
    ap.add_argument("--status", action="store_true", help="print device status instead")
    args = ap.parse_args()

    port = args.port or find_port()
    if not port:
        sys.exit("No serial port found. Pass one explicitly, e.g. python capture.py COM9")

    print(f"Opening {port} @ {args.baud} baud ...")
    lines = []
    host_start = None
    host_stop = None
    aborted = False
    state = "waiting"          # waiting -> armed -> recording -> stopping -> dumping
    start_watch = None
    stop_watch = None
    end_marker = "#STATUS_END" if args.status else "#CAPTURE_END"

    with serial.Serial(port, args.baud, timeout=0.2) as ser:
        time.sleep(1.5)        # some boards reset when the port opens
        ser.reset_input_buffer()
        ser.write(b"status\n" if args.status else b"capture\n")

        done = False
        while not done:
            try:
                # Act on Enter presses, checked on every pass
                if state == "armed" and start_watch.is_set():
                    ser.write(b"go\n")
                    state = "recording"
                    host_start = now_str()
                    print(f">>> [{host_start}] START sent. Press Enter to STOP early, or let it finish.")
                    stop_watch = enter_watcher()
                elif state == "recording" and stop_watch.is_set():
                    ser.write(b"stop\n")
                    state = "stopping"
                    print(f">>> [{now_str()}] STOP sent.")

                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                lines.append(line)
                print(line)

                if line.startswith(end_marker):
                    done = True
                elif line.startswith("#CAPTURE_ABORTED"):
                    aborted = True
                    done = True
                elif args.status:
                    pass
                elif line.startswith("#ARMED") and state == "waiting":
                    state = "armed"
                    start_watch = enter_watcher()
                    print(">>> Armed. Press Enter to START recording.")
                elif line.startswith("#RECORDING_END"):
                    host_stop = now_str()
                    state = "dumping"
                    print(f">>> [{host_stop}] RECORDING ENDED. Receiving data ...")

            except KeyboardInterrupt:
                if state == "recording":
                    ser.write(b"stop\n")
                    state = "stopping"
                    print("\n>>> Ctrl+C: stopping recording and saving.")
                elif state in ("waiting", "armed"):
                    ser.write(b"abort\n")
                    print("\n>>> Ctrl+C: aborting.")
                else:
                    print("\n>>> Ctrl+C: waiting for the device to finish ...")

    if args.status:
        return
    if aborted:
        print("Capture aborted. Nothing saved.")
        return

    os.makedirs(CAPTURE_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(CAPTURE_DIR, f"capture_{stamp}.txt")
    header = [f"#HOST_START {host_start or '?'}", f"#HOST_STOP {host_stop or '?'}"]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header + lines) + "\n")
    print(f"\nSaved {out_path}")
    print(f'Plot with:  python plot_capture.py "{out_path}"')


if __name__ == "__main__":
    main()