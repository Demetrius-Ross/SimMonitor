import network
import espnow
import machine
import ubinascii
import time
import struct  # For compact data struct packing

# === Initialize WiFi for ESP-NOW (STA Mode Required) ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# === Initialize ESP-NOW ===
esp = espnow.ESPNow()
esp.active(True)

# === Define GPIOs for Role & ID Assignment ===
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
unique_mac_prefix = mac_prefix.get(DEVICE_TYPE, "AC:DB:FF")
device_id_hex = "{:02X}".format(device_id)
unique_mac = "{}:{}:{}".format(unique_mac_prefix, device_id_hex, device_id_hex)

print(f"\n[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, MAC: {unique_mac}\n")

# === Define Receiver MAC Address (Updated with actual MAC) ===
receiver_mac = b'\xAC\xDB\x02\x01\x01'  # Replace with actual receiver MAC
esp.add_peer(receiver_mac)

# === Pin Definitions ===
RAMP_UP_PIN = machine.Pin(14, machine.Pin.IN)
RAMP_DOWN_PIN = machine.Pin(27, machine.Pin.IN)
SIM_HOME_PIN = machine.Pin(26, machine.Pin.IN)

# === Initialize Data Structures ===
previous_data = None  # Store last sent data
last_heartbeat = 0  # Track last heartbeat timestamp

# === Fix: Proper Serial Output for Debugging ===
print("[INFO] Serial output initialized. Logging messages...")

# === Helper Functions ===
def get_ramp_state():
    """Determine ramp state based on GPIO inputs"""
    ramp_up = RAMP_UP_PIN.value()
    ramp_down = RAMP_DOWN_PIN.value()

    if ramp_up == 1 and ramp_down == 1:
        return 0  # In Motion
    elif ramp_up == 0:
        return 1  # Ramp Up
    elif ramp_down == 0:
        return 2  # Ramp Down
    return 0  # Default to In Motion

def get_motion_state():
    """Determine motion state (1: Sim Down, 2: Sim Up)"""
    return 1 if SIM_HOME_PIN.value() == 0 else 2

def send_message(message_type="DATA"):
    """Constructs and sends a message with an identifier for data or heartbeat"""
    global previous_data
    msg_id = 0xA1 if message_type == "DATA" else 0xB1  # 0xA1 for data, 0xB1 for heartbeat

    device_id_byte = device_id & 0xFF  # Ensure fits 1 byte
    msg_id_byte = msg_id & 0xFF  # Ensure fits 1 byte
    ramp_state_short = get_ramp_state() & 0xFFFF  # Ensure 2-byte integer
    motion_state_short = get_motion_state() & 0xFFFF  # Ensure 2-byte integer

    try:
        data_packet = struct.pack(">BBHH", device_id_byte, msg_id_byte, ramp_state_short, motion_state_short)
    except Exception as e:
        print(f"[ERROR] struct.pack() failed: {e}")
        return
    
    # Avoid sending duplicate data messages
    if message_type == "DATA" and data_packet == previous_data:
        return

    result = esp.send(receiver_mac, data_packet)
    if result:
        print(f"[INFO] {message_type} Sent: {ubinascii.hexlify(data_packet).decode()}")
    else:
        print(f"[ERROR] Failed to send {message_type}, retrying...")
        esp.send(receiver_mac, data_packet)  # Retry

    # Update previous data for comparison
    if message_type == "DATA":
        previous_data = data_packet

# === Send Initial Boot Heartbeat ===
send_message("HEARTBEAT")
last_heartbeat = time.time()

# === Main Loop: Send Data When State Changes & Periodic Heartbeats ===
while True:
    send_message("DATA")

    # Send heartbeat every 30 seconds
    if time.time() - last_heartbeat >= 30:
        send_message("HEARTBEAT")
        last_heartbeat = time.time()

    time.sleep(0.05)  # Small delay to avoid flooding the network
