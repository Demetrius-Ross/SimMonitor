import network
import espnow
import machine
import ubinascii
import time
import struct

print("Starting Relay Node with Extra Debug...")

# === GPIO for Role & ID ===
role_pins = [machine.Pin(18, machine.Pin.IN), machine.Pin(19, machine.Pin.IN)]
id_pins = [machine.Pin(2, machine.Pin.IN),
           machine.Pin(4, machine.Pin.IN),
           machine.Pin(16, machine.Pin.IN),
           machine.Pin(17, machine.Pin.IN)]

role_value = (role_pins[0].value() << 1) | role_pins[1].value()
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))

if DEVICE_TYPE != "RELAY":
    print(f"[ERROR] This node is {DEVICE_TYPE}, not RELAY. Exiting.")
    raise SystemExit

print(f"[BOOT] Relay Node. ID={device_id}")

# === STA + AP for ESP-NOW
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=6)
ap = network.WLAN(network.AP_IF)
ap.active(True)

# === Initialize ESP-NOW
esp = espnow.ESPNow()
esp.active(True)
print("[INIT] ESP-NOW active on Relay")

# === Dictionary to store known peers
# key = virtual MAC string, val = { 'real_mac':..., 'hop':..., 'type':... }
known_peers = {}

# We consider AC:DB:02:01:01 the final receiver
FINAL_VMAC = "AC:DB:02:01:01"

# Add broadcast peer to receive identity packets
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
except:
    pass

# === Packet Formats
PACKET_FORMAT = ">16sBBHHH"  # 24 bytes for data/heartbeat
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)  # 24
IDENTITY_SIZE = 22             # 16s + 6s

def debug_print_peers():
    """Print out all known_peers for debugging."""
    print("=== Known Peers ===")
    for vmac, info in known_peers.items():
        print(f"  {vmac} => real_mac={ubinascii.hexlify(info['real_mac'])}, "
              f"hop={info['hop']}, type={info['type']}")
    print("===================")

def process_identity_packet(msg):
    """Unpack identity => store the peer's Virtual->Real mapping."""
    try:
        vmac_bytes, rmac = struct.unpack("16s6s", msg)
        vmac_str = vmac_bytes.decode().strip('\x00')

        # If not in known_peers, add with default hop=999
        if vmac_str not in known_peers:
            known_peers[vmac_str] = {
                'real_mac': rmac,
                'hop': 999,
                'type': "UNKNOWN"
            }
            try:
                esp.add_peer(rmac)
            except:
                pass

            # If it's the final receiver's vMAC => set hop=0, type=RECEIVER
            if vmac_str == FINAL_VMAC:
                known_peers[vmac_str]['hop'] = 0
                known_peers[vmac_str]['type'] = "RECEIVER"
                print(f"[IDENTITY] Found final receiver => {vmac_str}, hop=0")

            print(f"[IDENTITY] {vmac_str} => {ubinascii.hexlify(rmac)} stored (hop={known_peers[vmac_str]['hop']})")
        else:
            # Possibly update if it is the final receiver
            if vmac_str == FINAL_VMAC:
                known_peers[vmac_str]['hop'] = 0
                known_peers[vmac_str]['type'] = "RECEIVER"
                print(f"[IDENTITY] Re-discovered final receiver => {vmac_str}, hop=0")

    except Exception as e:
        print("[ERROR] Identity packet parse error:", e)

def forward_packet(dest_vmac, data_packet):
    """
    Attempt to send data_packet to final receiver or a next-hop relay.
    Returns True if successful, False if not.
    """
    debug_print_peers()

    # 1) If it's for final receiver, check if we have hop=0 => direct
    if dest_vmac == FINAL_VMAC and dest_vmac in known_peers:
        info = known_peers[dest_vmac]
        if info['hop'] < 999:
            rmac = info['real_mac']
            print(f"[FORWARD] Attempt direct to final receiver: {dest_vmac}, real_mac={ubinascii.hexlify(rmac)}")
            result = esp.send(rmac, data_packet)
            print(f"[FORWARD] Direct send result={result}")
            if result:
                print(f"[FORWARD] Delivered directly to final receiver {dest_vmac}")
                return True
            else:
                print("[WARN] Direct send to final receiver failed")
        else:
            print("[WARN] We have no good hop to final receiver yet (hop=999)")

    # 2) Otherwise, find a known relay with the best hop
    best_relay = None
    best_hop = 999
    for vmac_str, peer_info in known_peers.items():
        if peer_info['type'] == "RELAY" and peer_info['hop'] < best_hop:
            best_hop = peer_info['hop']
            best_relay = peer_info['real_mac']

    if best_relay:
        print(f"[FORWARD] Trying best relay (hop={best_hop}), real_mac={ubinascii.hexlify(best_relay)}")
        result = esp.send(best_relay, data_packet)
        print(f"[FORWARD] Relay send result={result}")
        if result:
            print("[FORWARD] Packet forwarded to next relay")
            return True
        else:
            print("[WARN] Forward to best relay failed")

    return False

def on_data_recv(*args):
    """
    Callback for ESP-NOW IRQ. 
    We must do peer, msg = esp.recv() to get the actual packet.
    """
    peer, msg = esp.recv()
    if not msg:
        return

    length = len(msg)
    if length == IDENTITY_SIZE:
        # Identity packet (22 bytes)
        process_identity_packet(msg)
    elif length == PACKET_SIZE:  # 24
        # Data or Heartbeat
        try:
            dest_field, sender_id, msg_type, ramp_state, motion_state, seq = struct.unpack(PACKET_FORMAT, msg)
            dest_vmac = dest_field.decode().strip('\x00')

            print(f"\n[RELAY] Got packet => Dest={dest_vmac}, SenderID={sender_id}, "
                  f"MsgType=0x{msg_type:02X}, Ramp={ramp_state}, Motion={motion_state}, Seq={seq}")

            # Attempt to forward
            if forward_packet(dest_vmac, msg):
                print(f"[RELAY] Forwarded msg_type=0x{msg_type:02X}, from SenderID={sender_id}, Seq={seq}")
            else:
                print("[RELAY] Forward attempt failed (no route or send error)")
        except Exception as e:
            print("[ERROR] Data packet parse error:", e)
    else:
        print(f"[WARN] Received packet with unexpected length: {length}")

# === Attach the new callback
esp.irq(on_data_recv)

print("[RELAY] Ready to forward messages...")

# Keep script alive
while True:
    time.sleep(1)
