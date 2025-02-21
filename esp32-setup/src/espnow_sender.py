import network
import espnow
import machine
import ubinascii
import time
import struct

print("Starting integrated sender...")

# --- Activate Dual Mode: STA + AP ---
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=6)
ap = network.WLAN(network.AP_IF)
ap.active(True)
print("Dual mode active:")
print("  STA MAC:", ubinascii.hexlify(sta.config('mac')))
print("  AP  MAC:", ubinascii.hexlify(ap.config('mac')))

# --- Initialize ESP-NOW ---
esp = espnow.ESPNow()
esp.active(True)
print("ESP-NOW Initialized")

# --- Define GPIOs for Role & ID Assignment ---
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]
id_pins = [
    machine.Pin(2, machine.Pin.IN),
    machine.Pin(4, machine.Pin.IN),
    machine.Pin(16, machine.Pin.IN),
    machine.Pin(17, machine.Pin.IN)
]

# --- Determine Role and Unique ID ---
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# --- Compute Virtual MAC ---
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02"}
virtual_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"
real_mac = ubinascii.hexlify(sta.config('mac'), ':').decode()
print(f"\n[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, Virtual MAC: {virtual_mac}, Real MAC: {real_mac}\n")

# --- Use Broadcast Address for ESP-NOW Sends ---
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
    print("[PEER] Broadcast peer added")
except Exception as e:
    print("[WARN] Could not add broadcast peer:", e)

# --- Global Sequence Counter for Data Messages ---
seq_counter = 0

# --- Identity Broadcast Function (22-byte packet) ---
def broadcast_identity():
    padded_vmac = virtual_mac.encode()
    if len(padded_vmac) < 16:
        padded_vmac += b'\x00' * (16 - len(padded_vmac))
    identity_packet = struct.pack("16s6s", padded_vmac, sta.config('mac'))
    try:
        if esp.send(broadcast_mac, identity_packet):
            print("[BROADCAST] Identity broadcast sent")
        else:
            print("[ERROR] Identity broadcast failed")
    except Exception as e:
        print("[ERROR] Exception during identity broadcast:", e)


# === Pin Definitions for Sensor Inputs ===
RAMP_UP_PIN = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN)
RAMP_DOWN_PIN = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_DOWN)
SIM_HOME_PIN = machine.Pin(26, machine.Pin.IN, machine.Pin.PULL_DOWN)

# --- Sensor Functions  ---
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

# --- Data Message Sending Function (24 bytes) ---
def send_data_message():
    global seq_counter
    msg_type = 0xA1  # Data message type; use 0xB1 for heartbeat if needed.
    # Intended destination's virtual MAC (e.g., receiver's):
    dest_virtual = "AC:DB:02:01:01"
    dest_field = dest_virtual.encode()
    if len(dest_field) < 16:
        dest_field += b'\x00' * (16 - len(dest_field))
    # Build the data packet (24 bytes):
    # Structure: Destination (16s) | Sender ID (B) | Msg Type (B) | Ramp State (H) | Motion State (H) | Sequence (H)
    packet = struct.pack(">16sBBHHH", dest_field, device_id, msg_type, get_ramp_state(), get_motion_state(), seq_counter)
    seq_counter = (seq_counter + 1) % 65536
    print("\n[SENDER] Sending Data Message")
    print("  Destination:", dest_virtual)
    print("  Packet (hex):", ubinascii.hexlify(packet))
    print("  Timestamp:", time.time())
    try:
        if esp.send(broadcast_mac, packet):
            print("[INFO] Data message sent successfully")
        else:
            print("[ERROR] Data message send failed")
    except Exception as e:
        print("[ERROR] Exception during data send:", e)

# --- Heartbeat Message Sending Function (24 bytes) ---
def send_heartbeat():
    global seq_counter
    msg_type = 0xB1  # Heartbeat message type.
    dest_virtual = "AC:DB:02:01:01"
    dest_field = dest_virtual.encode()
    if len(dest_field) < 16:
        dest_field += b'\x00' * (16 - len(dest_field))
    # Use the same structure, but with msg_type 0xB1.
    packet = struct.pack(">16sBBHHH", dest_field, device_id, msg_type, get_ramp_state(), get_motion_state(), seq_counter)
    seq_counter = (seq_counter + 1) % 65536
    print("\n[SENDER] Sending Heartbeat Message")
    print("  Destination:", dest_virtual)
    print("  Packet (hex):", ubinascii.hexlify(packet))
    print("  Timestamp:", time.time())
    try:
        if esp.send(broadcast_mac, packet):
            print("[INFO] Heartbeat message sent successfully")
        else:
            print("[ERROR] Heartbeat message send failed")
    except Exception as e:
        print("[ERROR] Exception during heartbeat send:", e)

# --- Main Loop ---
# Broadcast identity once at startup.
broadcast_identity()
last_identity_time = time.time()
last_heartbeat_time = time.time()

while True:
    # Update identity every 30 seconds.
    if time.time() - last_identity_time >= 30:
        broadcast_identity()
        last_identity_time = time.time()
    # Send heartbeat every 30 seconds.
    if time.time() - last_heartbeat_time >= 30:
        send_heartbeat()
        last_heartbeat_time = time.time()
    # Send a data message every 2 seconds.
    send_data_message()
    time.sleep(2)
