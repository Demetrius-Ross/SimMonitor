import network
import espnow
import machine
import ubinascii
import time
import struct
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=6)
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid="SimNode", hidden=1)
esp = espnow.ESPNow()
esp.active(True)
role_pins = [
    machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN), 
    machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_DOWN),
    machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN),
    ]
id_pins = [
    machine.Pin(4, machine.Pin.IN),
    machine.Pin(16, machine.Pin.IN),
    machine.Pin(17, machine.Pin.IN),
    machine.Pin(5, machine.Pin.IN, machine.Pin.PULL_DOWN)
]
role_value = (
    (role_pins[0].value() << 2) | 
    (role_pins[1].value() << 1) |
     role_pins[2].value()
)
roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER", 3: "TELEMETRY"}
DEVICE_TYPE = roles.get(role_value, "UNKNOWN")
device_id = sum(pin.value() << i for i, pin in enumerate(id_pins))
mac_prefix = {"SENDER": "AC:DB:00", "RELAY": "AC:DB:01", "RECEIVER": "AC:DB:02", "TELEMETRY": "AC:DB:03"}
virtual_mac = f"{mac_prefix[DEVICE_TYPE]}:{device_id:02X}:{device_id:02X}"
real_mac = ubinascii.hexlify(sta.config('mac'), ':').decode()
print(f"\n[BOOT] Role: {DEVICE_TYPE}, ID: {device_id}, Virtual MAC: {virtual_mac}, Real MAC: {real_mac}\n")
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
try:
    esp.add_peer(broadcast_mac)
except:
    pass
PACKET_FORMAT = ">16sBBHHH"
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)
IDENTITY_FORMAT = "16s6s"
IDENTITY_SIZE = struct.calcsize(IDENTITY_FORMAT)
def run_sender():
    def broadcast_identity():
        padded_vmac = virtual_mac.encode()
        if len(padded_vmac) < 16:
            padded_vmac += b'\x00' * (16 - len(padded_vmac))
        identity_packet = struct.pack(IDENTITY_FORMAT, padded_vmac, sta.config('mac'))
        try:
            if esp.send(broadcast_mac, identity_packet):
                print("[BROADCAST] Identity broadcast sent")
            else:
                print("[ERROR] Identity broadcast failed")
        except Exception as e:
            print("[ERROR] Exception during identity broadcast:", e)
    seq_counter = 0
    last_identity_time = time.time()
    last_heartbeat_time = time.time()
    RAMP_UP_PIN = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_DOWN)
    RAMP_DOWN_PIN = machine.Pin(25, machine.Pin.IN, machine.Pin.PULL_DOWN)
    SIM_HOME_PIN = machine.Pin(26, machine.Pin.IN, machine.Pin.PULL_DOWN)
    def get_ramp_state():
        ramp_up = RAMP_UP_PIN.value()
        ramp_down = RAMP_DOWN_PIN.value()
        if ramp_up == 1 and ramp_down == 1:
            return 0
        elif ramp_up == 0:
            return 1
        elif ramp_down == 0:
            return 2
        return 0
    def get_motion_state():
        return 1 if SIM_HOME_PIN.value() == 0 else 2
    def send_data_message():
        nonlocal seq_counter
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
        try:
            if esp.send(broadcast_mac, packet):
                print("[INFO] Data message sent successfully")
            else:
                print("[ERROR] Data message send failed")
        except Exception as e:
            print("[ERROR] Exception during data send:", e)
    def send_heartbeat():
        nonlocal seq_counter
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
        try:
            if esp.send(broadcast_mac, packet):
                print("[INFO] Heartbeat message sent successfully")
            else:
                print("[ERROR] Heartbeat message send failed")
        except Exception as e:
            print("[ERROR] Exception during heartbeat send:", e)
    prev_ramp_state = None
    prev_motion_state = None
    while True:
        if time.time() - last_identity_time >= 30:
            broadcast_identity()
            last_identity_time = time.time()
        if time.time() - last_heartbeat_time >= 30:
            send_heartbeat()
            last_heartbeat_time = time.time()
        current_ramp = get_ramp_state()
        current_motion = get_motion_state()
        if (prev_ramp_state is None or
            current_ramp != prev_ramp_state or
            current_motion != prev_motion_state):
            send_data_message()
            prev_ramp_state = current_ramp
            prev_motion_state = current_motion
        time.sleep(2)
def run_relay():
    known_peers = {}
    FINAL_VMAC = "AC:DB:02:01:01"
    def process_identity_packet(msg):
        try:
            vmac_bytes, rmac = struct.unpack(IDENTITY_FORMAT, msg)
            vmac_str = vmac_bytes.decode().strip('\x00')
            if vmac_str not in known_peers:
                known_peers[vmac_str] = {'real_mac': rmac, 'hop': 999, 'type': "UNKNOWN"}
                try:
                    esp.add_peer(rmac)
                except:
                    pass
                if vmac_str == FINAL_VMAC:
                    known_peers[vmac_str]['hop'] = 0
                    known_peers[vmac_str]['type'] = "RECEIVER"
                    print(f"[IDENTITY] Found final receiver => {vmac_str}, hop=0")
                print(f"[IDENTITY] {vmac_str} => {ubinascii.hexlify(rmac)} stored")
        except Exception as e:
            print("[ERROR] Identity packet parse error:", e)
    def forward_packet(dest_vmac, data_packet):
        print("=== Known Peers ===")
        for vmac, info in known_peers.items():
            print(f"  {vmac} => {ubinascii.hexlify(info['real_mac'])}, hop={info['hop']}, type={info['type']}")
        print("===================")
        if dest_vmac == FINAL_VMAC and dest_vmac in known_peers:
            info = known_peers[dest_vmac]
            if info['hop'] < 999:
                rmac = info['real_mac']
                print(f"[FORWARD] Attempt direct to final receiver: {dest_vmac}")
                if esp.send(rmac, data_packet):
                    print(f"[FORWARD] Delivered to final receiver {dest_vmac}")
                    return True
                else:
                    print("[WARN] Direct send to final receiver failed")
            else:
                print("[WARN] No good hop to final receiver yet (hop=999)")
        best_relay = None
        best_hop = 999
        for vmac_str, peer_info in known_peers.items():
            if peer_info['type'] == "RELAY" and peer_info['hop'] < best_hop:
                best_hop = peer_info['hop']
                best_relay = peer_info['real_mac']
        if best_relay:
            print(f"[FORWARD] Trying best relay (hop={best_hop})")
            if esp.send(best_relay, data_packet):
                print("[FORWARD] Packet forwarded to next relay")
                return True
            else:
                print("[WARN] Forward to best relay failed")
        return False
    def on_data_recv(*args):
        peer, msg = esp.recv()
        if not msg:
            return
        length = len(msg)
        if length == IDENTITY_SIZE:
            process_identity_packet(msg)
        elif length == PACKET_SIZE:
            try:
                dest_field, sender_id, msg_type, ramp_state, motion_state, seq = struct.unpack(PACKET_FORMAT, msg)
                dest_vmac = dest_field.decode().strip('\x00')
                print(f"\n[RELAY] Got => Dest={dest_vmac}, SenderID={sender_id}, MsgType=0x{msg_type:02X}")
                if forward_packet(dest_vmac, msg):
                    print(f"[RELAY] Forwarded msg_type=0x{msg_type:02X}, from SenderID={sender_id}, Seq={seq}")
                else:
                    print("[RELAY] Forward attempt failed (no route or send error)")
            except Exception as e:
                print("[ERROR] Data parse error:", e)
        else:
            print(f"[WARN] Received packet with unexpected length: {length}")
    esp.irq(on_data_recv)
    print("[RELAY] Ready to forward messages...")
    while True:
        time.sleep(1)
def run_receiver():
    def broadcast_receiver_identity():
        vmac_bytes = virtual_mac.encode()
        if len(vmac_bytes) < 16:
            vmac_bytes += b'\x00' * (16 - len(vmac_bytes))
        identity_packet = struct.pack(IDENTITY_FORMAT, vmac_bytes, sta.config('mac'))
        try:
            if esp.send(b'\xff\xff\xff\xff\xff\xff', identity_packet):
                print(f"[BROADCAST] Receiver identity: {virtual_mac}")
            else:
                print("[ERROR] Identity broadcast failed")
        except Exception as e:
            print("[ERROR] Exception during identity broadcast:", e)
    last_broadcast_time = time.time()
    while True:
        if time.time() - last_broadcast_time >= 30:
            broadcast_receiver_identity()
            last_broadcast_time = time.time()
        peer, msg = esp.recv()
        if msg:
            length = len(msg)
            if length == PACKET_SIZE:
                try:
                    dest_field, sender_id_val, msg_type, ramp_state, motion_state, seq = struct.unpack(PACKET_FORMAT, msg)
                    dest_virtual = dest_field.decode().strip('\x00')
                    if dest_virtual == virtual_mac:
                        if msg_type == 0xA1:
                            print(f"[DATA] Received from Sender ID {sender_id_val}: "
                                  f"RampState={ramp_state}, MotionState={motion_state}, Seq={seq}")
                        elif msg_type == 0xB1:
                            print(f"[HEARTBEAT] Received from Sender ID {sender_id_val}: "
                                  f"RampState={ramp_state}, MotionState={motion_state}, Seq={seq}")
                        else:
                            print(f"[INFO] Unknown msg type 0x{msg_type:02X}")
                    else:
                        print(f"[INFO] Ignored message for {dest_virtual}")
                except Exception as e:
                    print("[ERROR] Unpack data error:", e)
            elif length == IDENTITY_SIZE:
                try:
                    vmac_bytes, rmac = struct.unpack(IDENTITY_FORMAT, msg)
                    vmac = vmac_bytes.decode().strip('\x00')
                    print(f"[IDENTITY] {vmac} => {ubinascii.hexlify(rmac).decode()}")
                    if vmac != virtual_mac:
                        if not esp.get_peer(rmac):
                            try:
                                esp.add_peer(rmac)
                                print(f"[PEER] Added {vmac} as peer")
                            except Exception as e:
                                print(f"[ERROR] Failed to add peer: {e}")
                except Exception as e:
                    print("[ERROR] Identity parse error:", e)
            else:
                print(f"[WARN] Received msg with unexpected length: {length}")
        time.sleep(0.05)
if DEVICE_TYPE == "SENDER":
    run_sender()
elif DEVICE_TYPE == "RELAY":
    run_relay()
elif DEVICE_TYPE == "RECEIVER":
    run_receiver()
else:
    print("[ERROR] Unknown role. Exiting.")
