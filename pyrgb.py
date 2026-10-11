import serial
import time
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor

# === CONFIGURATION ===
SERIAL_PORT = "COM10"      # Change to your Arduino COM port
BAUD_RATE = 115200
UPDATE_INTERVAL = 0.1      # seconds between updates
OPENRGB_IP = "localhost"   # or your OpenRGB host
OPENRGB_PORT = 6745        # default SDK port

# === CONNECT TO ARDUINO ===
print(f"Connecting to Arduino on {SERIAL_PORT}...")
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)

# === CONNECT TO OPENRGB SDK SERVER ===
print("Connecting to OpenRGB SDK server...")
client = OpenRGBClient(address=OPENRGB_IP, port=OPENRGB_PORT, name="ArduinoRGBBridge")
print("Connected to OpenRGB SDK server.")

devices = client.devices
print(f"Found {len(devices)} devices:")
for i, d in enumerate(devices):
    print(f" {i}: {d.name} ({len(d.colors)} LEDs)")

# === STREAM COLORS TO ARDUINO ===
print("Streaming average OpenRGB color to Arduino... (Ctrl+C to stop)")
try:
    while True:
        if len(devices) == 0:
            continue

        # Take colors from the first device
        device = devices[0]

        if len(device.colors) > 0:
            avg_r = int(sum(c.red for c in device.colors) / len(device.colors))
            avg_g = int(sum(c.green for c in device.colors) / len(device.colors))
            avg_b = int(sum(c.blue for c in device.colors) / len(device.colors))

            color_string = f"{avg_r},{avg_g},{avg_b}\n"
            ser.write(color_string.encode('utf-8'))

        time.sleep(UPDATE_INTERVAL)

except KeyboardInterrupt:
    print("\nStopped.")
    ser.close()
