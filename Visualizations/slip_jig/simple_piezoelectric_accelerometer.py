#!/usr/bin/env python3
"""
Live plot of accelerometer and piezo vibration sensor.  (DEBUG build)

Expects CSV lines from the firmware:  t_us,ax,ay,az,piezo,piezo_pp
Usage:  python live_plot_debug.py [PORT]      (close the plot window or press Ctrl+C to stop)
Close the PlatformIO serial monitor first - only one program can use the port.
"""
import sys
import time
from collections import deque

import matplotlib.pyplot as plt
import numpy as np
import serial
import serial.tools.list_ports

BAUD_RATE = 250000      # must match Serial.begin() in the firmware
V_REF = 5.0             # ADC reference voltage
ADC_MAX = 1023.0        # 10-bit ADC
COUNTS_PER_G = 1024.0   # MMA8452Q 12-bit, +/-2 g (use 4096 for MMA8451Q)
WINDOW_S = 5.0          # seconds of history shown
UPDATE_S = 0.05         # redraw interval

# --- DEBUG helpers -----------------------------------------------------------
DEBUG = True
_t0 = time.time()


def dbg(msg):
    if DEBUG:
        print(f"[DBG {time.time() - _t0:7.3f}s] {msg}", flush=True)


# counters reset every STATS_EVERY seconds
STATS_EVERY = 1.0
st = dict(bytes=0, ok=0, bad=0, loops=0, draws=0,
          t_read=0.0, t_draw=0.0, t_pause=0.0, max_gap=0.0)
total_bytes = 0
total_ok = 0
bad_printed = 0          # only print the first few bad lines
MAX_BAD_PRINT = 10
first_ok_printed = False
# -----------------------------------------------------------------------------


def get_port():
    ports = list(serial.tools.list_ports.comports())
    dbg(f"{len(ports)} serial port(s) found:")
    for p in ports:
        dbg(f"   {p.device:<10} desc={p.description!r} mfr={p.manufacturer!r} hwid={p.hwid!r}")
    for p in ports:
        if any(k in (p.description or "") for k in ["Arduino", "CH340", "USB", "Serial"]):
            dbg(f"auto-selected {p.device} (matched keyword in {p.description!r})")
            return p.device
    if ports:
        dbg(f"no keyword match, falling back to first port {ports[0].device}")
    return ports[0].device if ports else None


dbg(f"python {sys.version.split()[0]}, matplotlib backend will be: {plt.get_backend()}")
dbg(f"pyserial {serial.__version__}")
port = sys.argv[1] if len(sys.argv) > 1 else get_port()
if not port:
    sys.exit("[ERROR] No serial port found. Pass it as an argument, e.g. python live_plot.py COM4")

dbg(f"opening {port} @ {BAUD_RATE} ...  (if the script hangs HERE, the port itself is blocking)")
ser = serial.Serial(port, BAUD_RATE, timeout=0.01)
dbg("port opened")
print(f"Connected to {port} at {BAUD_RATE} baud. Close the plot window or press Ctrl+C to stop.")
dbg("sleeping 2 s for Arduino auto-reset ...")
time.sleep(2.0)  # many Arduino boards reset when the port is opened
dbg(f"in_waiting before flush: {ser.in_waiting} bytes")
ser.reset_input_buffer()
dbg("input buffer flushed")

# --- Data buffers ---
MAXLEN = 20000
t, ax_, ay_, az_, pz, pp = (deque(maxlen=MAXLEN) for _ in range(6))
buf = b""
synced = False      # drop the first (probably partial) line
t_prev_us = None
t_now = 0.0         # running time in seconds (handles micros() wrap-around)


def read_serial():
    global buf, synced, t_prev_us, t_now, total_bytes, total_ok, bad_printed, first_ok_printed
    waiting = ser.in_waiting
    data = ser.read(max(waiting, 1))
    st["bytes"] += len(data)
    total_bytes += len(data)
    if total_bytes and st["bytes"] == len(data) and total_bytes == len(data):
        dbg(f"first bytes received: {data[:60]!r}")
    buf += data
    if not synced:
        if b"\n" not in buf:
            return
        buf = buf.split(b"\n", 1)[1]
        synced = True
        dbg("synced to first newline (partial first line dropped)")
    *lines, buf = buf.split(b"\n")
    if len(buf) > 2000:
        dbg(f"WARNING: {len(buf)} bytes buffered with no newline - wrong baud rate or firmware not using println? "
            f"head={buf[:60]!r}")
    for line in lines:
        parts = line.decode("ascii", errors="ignore").strip().split(",")
        if len(parts) != 6:
            st["bad"] += 1
            if bad_printed < MAX_BAD_PRINT:
                bad_printed += 1
                dbg(f"BAD line (expected 6 fields, got {len(parts)}): {line[:80]!r}")
            continue
        try:
            t_us, ax, ay, az, piezo, pk = (float(p) for p in parts)
        except ValueError:  # header line or corrupted line
            st["bad"] += 1
            if bad_printed < MAX_BAD_PRINT:
                bad_printed += 1
                dbg(f"BAD line (not numeric): {line[:80]!r}")
            continue
        if not first_ok_printed:
            first_ok_printed = True
            dbg(f"FIRST VALID LINE: {line.strip()!r}")
        st["ok"] += 1
        total_ok += 1
        if t_prev_us is not None:
            t_now += ((t_us - t_prev_us) % 2 ** 32) / 1e6
        t_prev_us = t_us
        t.append(t_now)
        ax_.append(ax / COUNTS_PER_G)
        ay_.append(ay / COUNTS_PER_G)
        az_.append(az / COUNTS_PER_G)
        pz.append(piezo * V_REF / ADC_MAX)
        pp.append(pk * V_REF / ADC_MAX)


def fit_ylim(axis, arrays, min_span, zero_floor=False):
    lo = min(a.min() for a in arrays)
    hi = max(a.max() for a in arrays)
    if zero_floor:
        lo = 0.0
    if hi - lo < min_span:
        mid = (hi + lo) / 2
        lo, hi = mid - min_span / 2, mid + min_span / 2
    pad = 0.08 * (hi - lo)
    axis.set_ylim(lo - (0 if zero_floor else pad), hi + pad)


# --- Plot setup ---
dbg("creating figure ...")
plt.ion()
fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 7), sharex=True)
l_x, = a1.plot([], [], lw=0.9, label="X")
l_y, = a1.plot([], [], lw=0.9, label="Y")
l_z, = a1.plot([], [], lw=0.9, label="Z")
l_pz, = a2.plot([], [], color="orange", lw=1.0)
l_pp, = a3.plot([], [], color="dodgerblue", lw=1.0)

a1.set_title("Accelerometer X/Y/Z")
a1.set_ylabel("Accel (g)")
a1.legend(loc="upper left", ncol=3)
a2.set_title("Piezo (latest sample)")
a2.set_ylabel("Voltage (V)")
a3.set_title("Piezo peak-to-peak (fast sampling)")
a3.set_ylabel("Voltage (V)")
a3.set_xlabel("Time (seconds, 0 = now)")
a1.set_xlim(-WINDOW_S, 0)
for a in (a1, a2, a3):
    a.grid(True, linestyle="--", alpha=0.5)
fig.tight_layout()
dbg("figure created; entering main loop")
dbg("NOTE: if you never see a 'STATS' line below, the loop is stuck in a blocking call "
    "(last DBG line above tells you where)")

last_draw = 0.0
last_stats = time.time()
last_iter = time.time()
try:
    while plt.fignum_exists(fig.number):
        now_iter = time.time()
        st["max_gap"] = max(st["max_gap"], now_iter - last_iter)
        last_iter = now_iter
        st["loops"] += 1

        t1 = time.time()
        read_serial()
        st["t_read"] += time.time() - t1

        # periodic stats line
        if time.time() - last_stats >= STATS_EVERY:
            dt = time.time() - last_stats
            dbg(f"STATS {dt:.1f}s: loops={st['loops']} bytes={st['bytes']} ({st['bytes']/dt:.0f} B/s) "
                f"ok_lines={st['ok']} bad_lines={st['bad']} draws={st['draws']} "
                f"buffered={len(t)} | time: read={st['t_read']*1000:.0f}ms "
                f"draw={st['t_draw']*1000:.0f}ms pause={st['t_pause']*1000:.0f}ms "
                f"max_loop_gap={st['max_gap']*1000:.0f}ms")
            if st["bytes"] == 0:
                dbg("  -> NO BYTES this interval: board silent / wrong port / port in use / firmware not printing")
            elif st["ok"] == 0:
                dbg("  -> bytes arriving but 0 valid lines: format or baud mismatch")
            if st["loops"] > 0 and st["t_pause"] == 0.0:
                dbg("  -> plt.pause() was never called this interval: GUI is NOT being serviced "
                    "(this is what causes 'Not Responding')")
            for k in st:
                st[k] = 0.0 if isinstance(st[k], float) else 0
            last_stats = time.time()

        if time.time() - last_draw < UPDATE_S or len(t) < 3:
            continue
        last_draw = time.time()

        t2 = time.time()
        tt = np.array(t)
        keep = tt >= tt[-1] - WINDOW_S
        x = tt[keep] - tt[-1]
        X, Y, Z = (np.array(d)[keep] for d in (ax_, ay_, az_))
        P, K = np.array(pz)[keep], np.array(pp)[keep]

        l_x.set_data(x, X)
        l_y.set_data(x, Y)
        l_z.set_data(x, Z)
        l_pz.set_data(x, P)
        l_pp.set_data(x, K)
        fit_ylim(a1, (X, Y, Z), 0.05)
        fit_ylim(a2, (P,), 0.1)
        fit_ylim(a3, (K,), 0.1, zero_floor=True)

        recent = tt >= tt[-1] - 1.0
        span = tt[-1] - tt[recent][0]
        rate = (recent.sum() - 1) / span if span > 0 else 0
        a1.set_title(f"Accelerometer X/Y/Z ({rate:.0f} lines/s)")
        st["t_draw"] += time.time() - t2

        t3 = time.time()
        plt.pause(0.001)
        st["t_pause"] += time.time() - t3
        st["draws"] += 1
except KeyboardInterrupt:
    dbg("KeyboardInterrupt")
finally:
    ser.close()
    dbg(f"totals: bytes={total_bytes} valid_lines={total_ok}")
    print("Stopped.")