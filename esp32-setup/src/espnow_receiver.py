import network
import espnow
import ubinascii
import time
import struct
import machine

print("Starting integrated receiver (line-based logs)...")

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

# --- Define GPIOs for Role & ID ---
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]
#role_pins = [machine.Pin(33, machine.Pin.IN), machine.Pin(25, machine.Pin.IN)]
id_pins = [machine.Pin(2, machine.Pin.IN),
           machine.Pin(4, machine.Pin.IN),
           machine.Pin(16, machine.Pin.IN),
           machine.Pin(17, machine.Pin.IN)]

#id_pins = [machine.Pin(26, machine.Pin.IN),
           #machine.Pin(27, machine.Pin.IN),
           #machine.Pin(14, machine.Pin.IN),
           #machine.Pin(12, machine.Pin.IN)]

role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02"}
virtual_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"
real_mac_str = ubinascii.hexlify(sta.config('mac'), ':').decode()
print(f"\n[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, Virtual MAC: {virtual_mac}, Real MAC: {real_mac_str}\n")

# --- Add Broadcast Peer ---
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
    print("[PEER] Broadcast peer added on Receiver")
except Exception as e:
    print("[WARN] Could not add Broadcast peer:", e)

print("Receiver is ready, waiting for ESP-NOW packets...")

# === We define a function to broadcast this receiver's identity
def broadcast_receiver_identity():
    """Periodically broadcast the receiver's identity so relays can discover us."""
    vmac_bytes = virtual_mac.encode()
    if len(vmac_bytes) < 16:
        vmac_bytes += b'\x00' * (16 - len(vmac_bytes))
    # identity packet = 16s + 6s
    identity_packet = struct.pack("16s6s", vmac_bytes, sta.config('mac'))
    try:
        if esp.send(broadcast_mac, identity_packet):
            print(f"[BROADCAST] Receiver identity broadcast sent: {virtual_mac}")
        else:
            print("[ERROR] Identity broadcast failed")
    except Exception as e:
        print("[ERROR] Exception during identity broadcast:", e)

# === Packet Format for Data/Heartbeat (24 bytes)
PACKET_FORMAT = ">16sBBHHH"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)

last_broadcast_time = time.time()

while True:
    # Periodically broadcast identity (e.g., every 30s)
    if time.time() - last_broadcast_time >= 30:
        broadcast_receiver_identity()
        last_broadcast_time = time.time()

    try:
        peer, msg = esp.recv()
        if msg:
            length = len(msg)
            if length == PACKET_SIZE:
                # Data or Heartbeat
                try:
                    dest_field, sender_id_val, msg_type, ramp_state, motion_state, seq = struct.unpack(
                        PACKET_FORMAT, msg
                    )
                    dest_virtual = dest_field.decode().strip('\x00')
                    if dest_virtual == virtual_mac:
                        # It's truly for us
                        if msg_type == 0xA1:
                            print(f"[DATA] Received from Sender ID {sender_id_val}: "
                                  f"RampState={ramp_state}, MotionState={motion_state}, Seq={seq}")
                        elif msg_type == 0xB1:
                            print(f"[HEARTBEAT] Received from Sender ID {sender_id_val}: "
                                  f"RampState={ramp_state}, MotionState={motion_state}, Seq={seq}")
                        else:
                            print(f"[INFO] Unknown msg type 0x{msg_type:02X} from Sender ID {sender_id_val}")
                    else:
                        print(f"[INFO] Ignored data message for destination {dest_virtual}")
                except Exception as e:
                    print("[ERROR] Unpack data message error:", e)
            elif length == 22:
                # Identity packet from a sender or another device
                try:
                    vmac_bytes, rmac = struct.unpack("16s6s", msg)
                    vmac = vmac_bytes.decode().strip('\x00')
                    print(f"[IDENTITY] Received identity: {vmac} -> {ubinascii.hexlify(rmac).decode()}")
                    # Optionally add to peer list
                    if vmac != virtual_mac:
                        if not esp.get_peer(rmac):
                            try:
                                esp.add_peer(rmac)
                                print(f"[PEER] Added {vmac} as peer")
                            except Exception as e:
                                print(f"[ERROR] Failed to add {vmac} as peer: {e}")
                except Exception as e:
                    print("[ERROR] Unpack identity message error:", e)
            else:
                print(f"[WARN] Received message with unexpected length: {length}")
    except Exception as e:
        print("[ERROR] esp.recv() error:", e)

    time.sleep(0.05)
