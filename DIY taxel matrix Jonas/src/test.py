import serial
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import time

# Serial port configuration
SERIAL_PORT = 'COM4'  # Replace with your port (e.g., '/dev/ttyUSB0' on Linux/Mac)
BAUD_RATE = 115200

# Heatmap dimensions (2 rows x 6 columns)
ROWS = 2
COLS = 6

def parse_heatmap(serial_data):
    lines = serial_data.strip().split('\n')
    heatmap = []

    for line in lines:
        if not line.strip() or "Heatmap" in line:
            continue
        try:
            values = list(map(int, line.strip().split()))
            if len(values) == COLS:
                heatmap.append(values)
        except ValueError:
            continue  # Ignore lines that don't parse

    return np.array(heatmap)

def main():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Allow Arduino time to reset

    plt.ion()
    fig, ax = plt.subplots()
    heatmap = np.zeros((ROWS, COLS))
    im = ax.imshow(heatmap, cmap='binary', vmin=0, vmax=1023)

    while True:
        try:
            raw_data = ser.read(ser.inWaiting()).decode('utf-8', errors='ignore')
            new_heatmap = parse_heatmap(raw_data)
            if new_heatmap.shape == (ROWS, COLS):
                im.set_data(new_heatmap)
                ax.set_title("Live Heatmap from Arduino")
                plt.draw()
                plt.pause(0.05)
        except KeyboardInterrupt:
            print("Exiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue

    ser.close()

if __name__ == "__main__":
    main()