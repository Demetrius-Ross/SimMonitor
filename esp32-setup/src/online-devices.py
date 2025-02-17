import time
import serial
import collections

# === Serial Port Configuration ===
SERIAL_PORT = "/dev/ttyUSB0"  # Change to match your ESP32's USB port
BAUD_RATE = 115200
TIMEOUT = 1  # 1 second timeout

# === Online Devices Storage ===
devices_online = collections.OrderedDict()  # Maintain order of received devices
DEVICE_TIMEOUT = 32  # Time in seconds before a device is considered offline

# === Open Serial Connection ===
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
    print(f"✅ Listening for ESP-NOW messages on {SERIAL_PORT}...\n")
except serial.SerialException:
    print(f"❌ Failed to open {SERIAL_PORT}. Check if the ESP32 is connected.")
    exit(1)

def check_offline_devices():
    """Remove devices that haven't sent data within the timeout period."""
    current_time = time.time()
    offline_devices = [device for device, last_seen in devices_online.items() if current_time - last_seen > DEVICE_TIMEOUT]

    for device in offline_devices:
        print(f"⚠️ [OFFLINE] Device {device} is no longer responding.")
        del devices_online[device]

# === Main Loop ===
while True:
    try:
        line = ser.readline().decode().strip()  # Read incoming serial data
        if line:
            parts = line.split(",")  # Expected format: device_id, ramp_state, motion_state
            if len(parts) >= 1:
                device_id = parts[0]  # Extract device ID
                devices_online[device_id] = time.time()  # Update last seen time
                print(f"🟢 [ONLINE] {line}")  # Print received message

        check_offline_devices()  # Check for offline devices
        time.sleep(1)  # Polling interval

    except KeyboardInterrupt:
        print("\n🔌 Exiting program...")
        ser.close()
        break
    except Exception as e:
        print(f"❌ Error: {e}")
        time.sleep(1)
