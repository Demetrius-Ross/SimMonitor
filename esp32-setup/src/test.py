import network
import espnow
import ubinascii
import time
import struct
import machine

print("Starting integrated receiver (polling mode with offline detection)...")

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

# --- Read Role and Unique ID ---
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# --- Compute Virtual MAC ---
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02"}
virtual_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"
real_mac_str = ubinascii.hexlify(sta.config('mac'), ':').decode()
print(f"\n[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, Virtual MAC: {virtual_mac}, Real MAC: {real_mac_str}\n")

# --- Dynamic MAC Resolution Table ---
mac_resolution_table = {}

# --- Active Devices for Heartbeat Tracking ---
# Keys: sender ID; Values: last heartbeat timestamp.
active_devices = {}

# --- Use Broadcast Address for ESP-NOW Sends ---
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
    print("[PEER] Broadcast peer added on Receiver")
except Exception as e:
    print("[WARN] Could not add broadcast peer:", e)

print("Receiver polling for messages...")

# --- Function to Process Identity Packets (22 bytes) ---
def process_identity_packet(msg):
    try:
        vmac_bytes, rmac = struct.unpack("16s6s", msg)
        vmac = vmac_bytes.decode().strip('\x00')
        print(f"[IDENTITY] Received identity: {vmac} -> {ubinascii.hexlify(rmac).decode()}")
        if vmac != virtual_mac:
            mac_resolution_table[vmac] = rmac
            print(f"[RESOLUTION] {vmac} resolved to {ubinascii.hexlify(rmac).decode()}")
            if not esp.get_peer(rmac):
                try:
                    esp.add_peer(rmac)
                    print(f"[PEER] Added {vmac} as peer")
                except Exception as e:
                    print(f"[ERROR] Failed to add {vmac} as peer: {e}")
    except Exception as e:
        # Ignore known ESP_ERR_ESPNOW_NOT_FOUND errors.
        if hasattr(e, "args") and e.args and e.args[0] == -12393:
            pass
        else:
            print(f"[ERROR] Unpack identity packet error: {e}")

# --- Function to Process Data/Heartbeat Messages (24 bytes) ---
def process_data_message(msg):
    try:
        # Data message structure (24 bytes):
        # Destination (16s) | Sender ID (B) | Msg Type (B) | Ramp State (H) | Motion State (H) | Sequence (H)
        dest_field, sender_id, msg_type, ramp_state, motion_state, seq = struct.unpack(">16sBBHHH", msg)
        dest_virtual = dest_field.decode().strip('\x00')
        if dest_virtual == virtual_mac:
            if msg_type == 0xA1:
                print(f"[DATA] Received from Sender ID {sender_id}: RampState={ramp_state}, MotionState={motion_state}, Seq={seq}")
            elif msg_type == 0xB1:
                print(f"[HEARTBEAT] Received from Sender ID {sender_id}, Seq={seq}")
                active_devices[sender_id] = time.time()
            else:
                print(f"[INFO] Unknown msg type {msg_type:02X} from Sender ID {sender_id}")
        else:
            print(f"[INFO] Ignored data message for destination {dest_virtual}")
    except Exception as e:
        print(f"[ERROR] Unpack data message error: {e}")

# --- Main Polling Loop ---
while True:
    try:
        peer, msg = esp.recv()
        if msg:
            length = len(msg)
            print(f"[POLL] Received message (length {length}): {ubinascii.hexlify(msg)}")
            if length == 24:
                process_data_message(msg)
            elif length == 22:
                process_identity_packet(msg)
            else:
                print(f"[WARN] Received message with unexpected length: {length}")
    except Exception as e:
        print(f"[ERROR] esp.recv() error: {e}")
    
    # Print current active_devices dictionary for debugging.
    print(f"[DEBUG] Active devices: {active_devices}")
    
    # Offline detection: Remove sender if no heartbeat in 60 seconds.
    current_time = time.time()
    for sender, last_seen in list(active_devices.items()):
        if current_time - last_seen > 60:
            print(f"[WARNING] Sender {sender} is offline (no heartbeat in 60s)")
            active_devices.pop(sender)
            # Optionally, remove from resolution table if desired.
    
    time.sleep(1)
