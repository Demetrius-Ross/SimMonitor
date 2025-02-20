import network
import espnow
import machine
import ubinascii
import time
import struct

# === Initialize WiFi for ESP-NOW ===
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.config(channel=6)
print("[INIT] WiFi set to STA mode on Channel 6")

# === Initialize ESP-NOW ===
esp = espnow.ESPNow()
esp.active(True)
print("[INIT] ESP-NOW Initialized")

# === Add Broadcast Address as Peer ===
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
    print("[PEER] Broadcast Address Added on Receiver")
except Exception as e:
    print("[ERROR] Failed to add Broadcast Peer:", e)

# === Define GPIOs for Role & ID Assignment ===
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]
id_pins = [machine.Pin(2, machine.Pin.IN), machine.Pin(4, machine.Pin.IN),
           machine.Pin(16, machine.Pin.IN), machine.Pin(17, machine.Pin.IN)]

# === Read Device Role from GPIO ===
role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# === Read Unique Device ID from GPIO ===
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

# === Virtual MAC Address Generation ===
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02"}
virtual_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"
real_mac_str = ubinascii.hexlify(wlan.config('mac'), ':').decode()
print(f"\n[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, Virtual MAC: {virtual_mac}, Real MAC: {real_mac_str}\n")

# === Dynamic MAC Resolution Table (for senders) ===
mac_resolution_table = {}

# Utility: Convert colon-separated MAC string to binary
def mac_str_to_bytes(mac_str):
    return ubinascii.unhexlify(mac_str.replace(":", ""))

# === Broadcast Identity ===
def broadcast_identity():
    identity_packet = struct.pack("16s6s", virtual_mac.encode(), wlan.config('mac'))
    try:
        if esp.send(broadcast_mac, identity_packet):
            print("[BROADCAST] Identity broadcast sent")
        else:
            print("[ERROR] Identity broadcast failed")
    except Exception as e:
        print("[ERROR] Exception during identity broadcast:", e)

# === Callback for Incoming Data Messages from Senders ===
def on_data_recv(peer, msg):
    if msg:
        try:
            sender_mac = ubinascii.hexlify(peer, ':').decode()
            data = struct.unpack(">BBHH", msg)
            sender_id = data[0]
            msg_type = data[1]  # 0xA1 = Data, 0xB1 = Heartbeat
            ramp_state = data[2]
            motion_state = data[3]
            if msg_type == 0xA1:
                print(f"[RECEIVED DATA] From ID {sender_id}: RampState={ramp_state}, MotionState={motion_state}")
            elif msg_type == 0xB1:
                print(f"[HEARTBEAT] From ID {sender_id}")
        except Exception as e:
            print("[ERROR] Failed to process incoming message:", e)

esp.irq(on_data_recv)

# === Listen for Broadcasts to Update Resolution Table ===
def listen_for_broadcasts():
    peer, msg = esp.recv()
    if msg:
        try:
            vmac_bytes, rmac = struct.unpack("16s6s", msg)
            vmac = vmac_bytes.decode().strip('\x00')
            # Ignore our own broadcast
            if vmac != virtual_mac:
                mac_resolution_table[vmac] = rmac
                print(f"[RESOLUTION] {vmac} resolved to {ubinascii.hexlify(rmac).decode()}")
                # Add sender as a peer if not already added
                if not esp.get_peer(rmac):
                    try:
                        esp.add_peer(rmac)
                        print(f"[PEER] Added sender {vmac} as Peer")
                    except Exception as e:
                        print(f"[ERROR] Failed to add sender {vmac} as peer: {e}")
        except Exception as e:
            print("[ERROR] Failed to parse broadcast message:", e)

# === Main Loop for Receiver (No Relay Section) ===
while True:
    broadcast_identity()      # Periodically announce our identity
    listen_for_broadcasts()   # Listen for incoming identity broadcasts
    time.sleep(2)
