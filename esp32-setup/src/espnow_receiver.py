import network
import espnow
import machine
import ubinascii
import time
import struct  # For unpacking data

# === Initialize WiFi in STA Mode (Required for ESP-NOW) ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(channel=6)  # Example: Channel 6

# === Initialize ESP-NOW ===
esp = espnow.ESPNow()
esp.active(True)

# === Define GPIOs for Role Identification ===
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]
id_pins = [machine.Pin(2, machine.Pin.IN), machine.Pin(4, machine.Pin.IN), machine.Pin(16, machine.Pin.IN), machine.Pin(17, machine.Pin.IN)]

# === Read Device Role from GPIO ===
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# === Read Unique Device ID from GPIO ===
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# === Get Base MAC Address ===
esp_mac = ubinascii.hexlify(wlan.config('mac'), ':').decode()

# === Assign MAC Prefix Based on Device Type ===
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02"}
# Ensure DEVICE_TYPE is valid, else fallback to "UNKNOWN"
if DEVICE_TYPE not in mac_prefix:
    print(f"[ERROR] Invalid DEVICE_TYPE detected: {DEVICE_TYPE}")
    DEVICE_TYPE = "UNKNOWN"

# Assign a fallback MAC in case of errors
unique_mac_prefix = mac_prefix.get(DEVICE_TYPE, "AC:DB:FF")

# Convert ID to Hexadecimal (Fix for MicroPython)
device_id_hex = "{:02X}".format(device_id)

# Correct MAC formatting (Fixing Syntax Error)
unique_mac = "{}:{}:{}".format(unique_mac_prefix, device_id_hex, device_id_hex)

print(f"\n[BOOT] Device Role: {DEVICE_TYPE}, ID: {device_id}, MAC: {unique_mac}\n")
# === Store Active Senders & Last Seen Timestamps ===
active_devices = {}  # {sender_id: last_seen_time}

def on_data_recv(peer, msg):
    """Handle incoming ESP-NOW messages."""
    global active_devices

    if msg:
        sender_mac = ubinascii.hexlify(peer, ':').decode()
        data = struct.unpack(">BBHH", msg)  # Unpack received data

        sender_id = data[0]
        msg_type = data[1]  # 0xA1 = Data, 0xB1 = Heartbeat
        ramp_state = data[2]
        motion_state = data[3]

        # Update last seen timestamp for this sender
        active_devices[sender_id] = time.time()

        if msg_type == 0xA1:  # Data Message
            msg_string = f"{sender_id},{ramp_state},{motion_state}"
            print(f"[RECEIVED DATA] {msg_string}")  # Directly prints instead of using UART.write()

        elif msg_type == 0xB1:  # Heartbeat Message
            print(f"[HEARTBEAT] Sender {sender_id} is online.")

# === Register ESP-NOW Receive Callback ===
esp.irq(on_data_recv)

print("[RECEIVER] Ready to process incoming messages.")

# === Monitor for Offline Devices & Automatic Reconnection ===
while True:
    current_time = time.time()
    for sender_id, last_seen in list(active_devices.items()):
        if current_time - last_seen > 60:  # Timeout threshold (60 seconds)
            print(f"[WARNING] Sender {sender_id} is OFFLINE (No heartbeat in 60s)")
            del active_devices[sender_id]

    time.sleep(5)  # Check every 5 seconds
