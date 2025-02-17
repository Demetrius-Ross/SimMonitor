import network
import espnow
import time

# Initialize WiFi and ESP-NOW
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

esp = espnow.ESPNow()
esp.active(True)

# Store last seen timestamps of devices
devices_online = {}

# Timeout settings (devices will be removed if no message is received within 15 seconds)
TIMEOUT = 15

print("Receiver is ready and listening for devices...")

while True:
    peer, msg = esp.recv()
    if msg:
        msg = msg.decode('utf-8')
        device_id = msg.split(" ")[0]  # Extract device ID
        devices_online[device_id] = time.time()  # Update last seen time

        print(f"[ONLINE] {msg}")

    # Check for timeouts
    current_time = time.time()
    for device in list(devices_online.keys()):
        if current_time - devices_online[device] > TIMEOUT:
            print(f"[OFFLINE] {device} is no longer responding.")
            del devices_online[device]  # Remove from active list

    time.sleep(1)
