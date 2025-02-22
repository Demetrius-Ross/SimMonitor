import network
import espnow
import machine
import ubinascii
import time
import struct

print("Starting Relay Node...")

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

print(f"[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}")

# We only proceed if this node is a RELAY
if DEVICE_TYPE != "RELAY":
    print("Not configured as RELAY. Exiting.")
    raise SystemExit

# === STA + AP for ESP-NOW ===
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=6)
ap = network.WLAN(network.AP_IF)
ap.active(True)

# === Initialize ESP-NOW ===
esp = espnow.ESPNow()
esp.active(True)
print("[INIT] ESP-NOW active on Relay")

# === Dictionary to store known peers and distances ===
# Key = Virtual MAC (like "AC:DB:00:01:01"), Value = dict with:
#   { 'real_mac': b'...', 'hop': <int>, 'type': "SENDER"/"RELAY"/"RECEIVER" }
known_peers = {}

# For final receiver we assume Virtual MAC = "AC:DB:02:01:01"
# We'll store the best known next hop. e.g. known_peers["AC:DB:02:01:01"] = { ... }

# === Add Broadcast MAC as a peer for receiving identity packets ===
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
except:
    pass

# === Packet Format for Identity (22 bytes) => 16s + 6s
# === Packet Format for Data/Heartbeat (24 bytes) => 16s + B + B + H + H + H
PACKET_FORMAT = ">16sBBHHH"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)

# === Relay Logic: if we get a packet for the final receiver and can't deliver,
# we forward it to another relay with fewer hops if known.
FINAL_VMAC = "AC:DB:02:01:01"  # Example final receiver's virtual MAC

def process_identity_packet(msg):
    """Unpack identity => store the peer's Virtual->Real mapping."""
    try:
        vmac_bytes, rmac = struct.unpack("16s6s", msg)
        vmac_str = vmac_bytes.decode().strip('\x00')

        # For demonstration, we assume each identity broadcast includes hop=1 if from the node itself.
        # In a more advanced approach, they'd broadcast their distance to the final receiver, etc.
        # We'll store them with hop=999 if we don't know better.
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

        print(f"[IDENTITY] {vmac_str} => {ubinascii.hexlify(rmac)} stored (hop=999 by default)")
    except Exception as e:
        print("[ERROR] Identity packet parse error:", e)

def forward_packet(dest_vmac, data_packet):
    """Attempt to send data_packet to the final receiver or a next-hop relay."""
    # If we know the final receiver's real_mac and hop < 999, try direct
    if dest_vmac == FINAL_VMAC and dest_vmac in known_peers:
        info = known_peers[dest_vmac]
        if info['hop'] < 999:
            rmac = info['real_mac']
            if esp.send(rmac, data_packet):
                print(f"[FORWARD] Delivered directly to final receiver {dest_vmac}")
                return True
            else:
                print("[WARN] Direct send to final receiver failed")
        else:
            print("[WARN] We have no good hop to final receiver yet")

    # Otherwise, find a known relay with a better hop
    best_relay = None
    best_hop = 999
    for vmac_str, peer_info in known_peers.items():
        if peer_info['type'] == "RELAY" and peer_info['hop'] < best_hop:
            best_hop = peer_info['hop']
            best_relay = peer_info['real_mac']

    if best_relay:
        print(f"[FORWARD] Trying best relay with hop={best_hop}")
        if esp.send(best_relay, data_packet):
            print("[FORWARD] Packet forwarded to relay")
            return True
        else:
            print("[WARN] Forward to best relay failed")
    return False

def on_data_recv(peer, msg):
    """Handle incoming packets on the relay."""
    if not msg:
        return

    length = len(msg)
    if length == 22:
        # Identity packet
        process_identity_packet(msg)
    elif length == PACKET_SIZE:
        # Data or Heartbeat
        try:
            dest_field, sender_id, msg_type, ramp_state, motion_state, seq = struct.unpack(PACKET_FORMAT, msg)
            dest_vmac = dest_field.decode().strip('\x00')

            # If we are a relay and the packet is not for us, attempt to forward
            if dest_vmac == FINAL_VMAC:
                # The final receiver
                # Attempt direct or via next-hop
                if forward_packet(dest_vmac, msg):
                    print(f"[RELAY] Forwarded msg_type=0x{msg_type:02X}, from SenderID={sender_id}, Seq={seq}")
                else:
                    print("[RELAY] Forward attempt failed (no route or send error)")
            else:
                # Possibly for another relay? We can attempt the same forward logic if we know the route
                if forward_packet(dest_vmac, msg):
                    print(f"[RELAY] Forwarded to next relay for {dest_vmac}")
                else:
                    print("[RELAY] No route to that destination or forward failed")

        except Exception as e:
            print("[ERROR] Data packet parse error:", e)
    else:
        print("[WARN] Received packet with unexpected length:", length)

def relay_main_loop():
    """Main loop for the relay."""
    while True:
        try:
            peer, msg = esp.recv()
            if msg:
                on_data_recv(peer, msg)
        except Exception as e:
            print("[ERROR] relay_main_loop error:", e)
        time.sleep(0.05)

# === Setup ESP-NOW callback
esp.irq(on_data_recv)

print("[RELAY] Ready to forward messages...")

# === A minimal loop to keep the code alive
relay_main_loop()
