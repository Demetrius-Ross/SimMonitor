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

# --- Global Sequence Counter ---
seq_counter = 0

# --- Identity Broadcast (22-byte packet) ---
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

# === Pin Definitions (with pull-down) ===
RAMP_UP_PIN = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN)
RAMP_DOWN_PIN = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_DOWN)
SIM_HOME_PIN = machine.Pin(26, machine.Pin.IN, machine.Pin.PULL_DOWN)

# === Sensor Functions ===
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

# === Data Message (24 bytes) ===
def send_data_message():
    """Send a 24-byte data packet (0xA1)."""
    global seq_counter
    msg_type = 0xA1
    dest_virtual = "AC:DB:02:01:01"
    dest_field = dest_virtual.encode()
    if len(dest_field) < 16:
        dest_field += b'\x00' * (16 - len(dest_field))

    packet = struct.pack(">16sBBHHH",
                         dest_field, device_id, msg_type,
                         get_ramp_state(), get_motion_state(), seq_counter)
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

# === Heartbeat Message (24 bytes) ===
def send_heartbeat():
    """Send a 24-byte heartbeat packet (0xB1)."""
    global seq_counter
    msg_type = 0xB1
    dest_virtual = "AC:DB:02:01:01"
    dest_field = dest_virtual.encode()
    if len(dest_field) < 16:
        dest_field += b'\x00' * (16 - len(dest_field))

    packet = struct.pack(">16sBBHHH",
                         dest_field, device_id, msg_type,
                         get_ramp_state(), get_motion_state(), seq_counter)
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

# --- Broadcast identity once at startup ---
broadcast_identity()
last_identity_time = time.time()

last_heartbeat_time = time.time()

# Keep track of previous ramp & motion to detect changes
prev_ramp_state = None
prev_motion_state = None

while True:
    # Identity broadcast every 30 seconds (optional)
    if time.time() - last_identity_time >= 30:
        broadcast_identity()
        last_identity_time = time.time()

    # Heartbeat every 30 seconds
    if time.time() - last_heartbeat_time >= 30:
        send_heartbeat()
        last_heartbeat_time = time.time()

    # Check current ramp & motion
    current_ramp = get_ramp_state()
    current_motion = get_motion_state()

    # If first iteration (prev_ramp_state is None) or there's a state change => send data
    if (prev_ramp_state is None or
        current_ramp != prev_ramp_state or
        current_motion != prev_motion_state):
        send_data_message()
        prev_ramp_state = current_ramp
        prev_motion_state = current_motion

    time.sleep(2)
