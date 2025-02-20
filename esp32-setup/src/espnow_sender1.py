import network
import espnow
import machine
import ubinascii
import time
import struct

# === Initialize WiFi for ESP-NOW (STA Mode Required) ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(channel=6)
print("[INIT] WiFi set to STA mode on Channel 6")

# === Initialize ESP-NOW ===
esp = espnow.ESPNow()
esp.active(True)
print("[INIT] ESP-NOW Initialized")

# === Define GPIOs for Role & ID Assignment ===
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]
id_pins = [
    machine.Pin(2, machine.Pin.IN),
    machine.Pin(4, machine.Pin.IN),
    machine.Pin(16, machine.Pin.IN),
    machine.Pin(17, machine.Pin.IN)
]

# === Read Device Role from GPIO ===
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# === Read Unique Device ID from GPIO ===
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# === Virtual MAC Address Generation ===
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02"}
virtual_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"
real_mac = ubinascii.hexlify(wlan.config('mac'), ':').decode()

print(f"\n[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, Virtual MAC: {virtual_mac}, Real MAC: {real_mac}\n")

# For broadcast-based communication, we use the broadcast MAC.
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'

# === Pin Definitions for Sensor Inputs ===
RAMP_UP_PIN = machine.Pin(14, machine.Pin.IN)
RAMP_DOWN_PIN = machine.Pin(27, machine.Pin.IN)
SIM_HOME_PIN = machine.Pin(26, machine.Pin.IN)

# === Helper Functions for Sensor States ===
def get_ramp_state():
    ramp_up = RAMP_UP_PIN.value()
    ramp_down = RAMP_DOWN_PIN.value()
    if ramp_up == 1 and ramp_down == 1:
        return 0  # In Motion
    elif ramp_up == 0:
        return 1  # Ramp Up
    elif ramp_down == 0:
        return 2  # Ramp Down
    return 0

def get_motion_state():
    return 1 if SIM_HOME_PIN.value() == 0 else 2

# === send_message() Using Broadcast with Embedded Destination Field ===
def send_message(message_type="DATA"):
    msg_id = 0xA1 if message_type == "DATA" else 0xB1  # Data or Heartbeat
    # Define the intended receiver's virtual MAC (update as needed)
    receiver_virtual_mac = "AC:DB:02:01:01"
    # Manually pad the destination field to 16 bytes
    dest_field = receiver_virtual_mac.encode()
    if len(dest_field) < 16:
        dest_field = dest_field + b'\x00' * (16 - len(dest_field))
    
    # Build packet:
    # Packet structure: Destination (16 bytes) | Sender ID (1 byte) | Message Type (1 byte) |
    #                  Ramp State (2 bytes) | Motion State (2 bytes)
    data_packet = struct.pack(">16sBBHH", dest_field, device_id, msg_id, get_ramp_state(), get_motion_state())

    print("\n[SENDER] Broadcasting Message")
    print(f"    ➡️ Using Broadcast MAC: {ubinascii.hexlify(broadcast_mac).decode()}")
    print(f"    📦 Packet Data (Hex): {ubinascii.hexlify(data_packet).decode()}")
    print(f"    🕒 Timestamp: {time.time()}")

    retry_count = 3
    for attempt in range(retry_count):
        try:
            result = esp.send(broadcast_mac, data_packet)
            if result:
                print(f"[INFO] {message_type} sent successfully on attempt {attempt + 1}")
                break
            else:
                print(f"[ERROR] {message_type} send attempt {attempt + 1} failed")
                time.sleep(0.2)
        except Exception as e:
            print(f"[ERROR] Exception during sending: {e}")
            time.sleep(0.2)

# === Main Loop: Send Data & Periodic Heartbeats ===
# Send an initial heartbeat
send_message("HEARTBEAT")
last_heartbeat = time.time()

while True:
    send_message("DATA")
    if time.time() - last_heartbeat >= 30:
        send_message("HEARTBEAT")
        last_heartbeat = time.time()
    time.sleep(0.05)
