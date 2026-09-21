import serial
import matplotlib.pyplot as plt
import numpy as np
import time

# Serial port configuration
SERIAL_PORT = 'COM5'  # Replace with your port (e.g., '/dev/ttyUSB0' on Linux/Mac)
BAUD_RATE = 9600

# Heatmap dimensions
ROWS = 4
COLS = 4

def parse_heatmap(ser):
    """Reads lines from serial until a complete matrix is collected."""
    # Wait until we see the start line
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line == "START":
            break

    heatmap = []
    # Read the next ROWS lines
    for _ in range(ROWS):
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        try:
            values = list(map(int, line.split()))
            if len(values) == COLS:
                heatmap.append(values)
        except ValueError:
            continue

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
            new_heatmap = parse_heatmap(ser)
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