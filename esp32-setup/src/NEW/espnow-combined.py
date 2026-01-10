# ------------------------------------------------------------
# Unified ESP-NOW firmware for SENDER / RELAY / RECEIVER (PATCHED)
#
# PATCH (Critical):
#   ✅ Replace blocking esp.recv() usage with non-blocking esp.recv(0)
#      so the receiver never “stalls” and stops printing R,1 / identity.
#
# KEEPING:
#   • MKIV vs Legacy detection + correct role/id logic
#   • MKIV-only RGB (WS2812/NeoPixel) support on GPIO27
#   • Real-MAC discovery via identity broadcasts
#   • Opportunistic unicast to known receiver MAC (less broadcast congestion)
#   • Relay uses IRQ -> queue -> main loop
#   • Receiver drains RX queue aggressively
#   • Heartbeats use jitter
#   • App-level PING/PONG verify
#   • Receiver outputs CSV serial:
#       R,1
#       O,<sid>,<0|1>
#       S,<sid>,<motion>,<ramp>,<seq>
# ------------------------------------------------------------

import network
import espnow
import machine
import ubinascii
import time
import struct
import urandom

# NeoPixel is used ONLY on MKIV; guarded import
try:
    import neopixel
except Exception:
    neopixel = None


# =========================================================
# Helpers
# =========================================================
def _ticks_ms():
    return time.ticks_ms()

def _ticks_diff(a, b):
    return time.ticks_diff(a, b)

def _pad16(b: bytes) -> bytes:
    if len(b) >= 16:
        return b[:16]
    return b + (b"\x00" * (16 - len(b)))

def _jitter_ms(max_ms=2000) -> int:
    return urandom.getrandbits(16) % max_ms

def _safe_hex_mac(mac_bytes: bytes) -> str:
    try:
        return ubinascii.hexlify(mac_bytes, ":").decode()
    except Exception:
        try:
            return ubinascii.hexlify(mac_bytes).decode()
        except Exception:
            return "??"

# =========================================================
# Wi-Fi / ESP-NOW init
# =========================================================
sta = network.WLAN(network.STA_IF)
sta.active(True)

# Reduce power-save latency if supported
try:
    sta.config(pm=0)
except Exception:
    pass

# NOTE: All devices must share the same channel for ESP-NOW.
sta.config(channel=6)

ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid="SimNode", hidden=1)

esp = espnow.ESPNow()
esp.active(True)

broadcast_mac = b"\xff\xff\xff\xff\xff\xff"
try:
    esp.add_peer(broadcast_mac)
except Exception:
    pass

# =========================================================
# PATCH: Non-blocking ESP-NOW receive wrapper
# =========================================================
def esp_recv_nb():
    """
    Returns (peer_mac, msg_bytes) or (None, None) when no message.

    On most ESP32 MicroPython builds:
      esp.recv(timeout_ms)
    exists and recv(0) is non-blocking.

    If your port does not accept an argument, we fall back to esp.recv()
    (which may block). But on ESP32 it is usually supported.
    """
    try:
        return esp.recv(0)  # Non-blocking: timeout 0ms
    except TypeError:
        # Port does not accept a timeout argument
        try:
            return esp.recv()
        except Exception:
            return (None, None)
    except Exception:
        return (None, None)


# =========================================================
# MKIV detect + role decode
# =========================================================
PIN19 = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_DOWN)  # MKIV flag pin (only high)
PIN18 = machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN)
PIN14 = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN)

time.sleep_ms(50)

mkiv_flag = (PIN19.value() == 1)

roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER", 3: "TELEMETRY"}

if mkiv_flag:
    # MKIV role uses GPIO18/GPIO14 (2-bit)
    role_value = (PIN18.value() << 1) | PIN14.value()
else:
    # Legacy role uses GPIO18/GPIO19 (2-bit)
    role_value = (PIN18.value() << 1) | PIN19.value()

DEVICE_TYPE = roles.get(role_value, "UNKNOWN")


# =========================================================
# Device ID decode (MKIV vs Legacy)
# =========================================================
if mkiv_flag:
    # MKIV current hex logic:
    # (NOTE: use your CURRENT working bit mapping)
    # A=GPIO17, B=GPIO5, C=GPIO4, D=GPIO16, then XOR invert

    A = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
    B = machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    C = machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    D = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)

    # Keeping your currently used mapping (as provided)
    raw_id = (
        (B.value() << 3) |
        (A.value() << 2) |
        (D.value() << 1) |
        C.value()
    )
    device_id = raw_id ^ 0x0F
else:
    # Legacy:
    # device_id = (GPIO4<<0)|(GPIO16<<1)|(GPIO17<<2)|(GPIO5<<3)
    P4  = machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    P16 = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)
    P17 = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
    P5  = machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN)

    raw_id = (P4.value() << 0) | (P16.value() << 1) | (P17.value() << 2) | (P5.value() << 3)
    device_id = raw_id


# =========================================================
# Virtual MAC scheme
# =========================================================
mac_prefix = {
    "SENDER":    "AC:DB:00",
    "RELAY":     "AC:DB:01",
    "RECEIVER":  "AC:DB:02",
    "TELEMETRY": "AC:DB:03",
}

virtual_mac = "{}:{:02X}:{:02X}".format(mac_prefix.get(DEVICE_TYPE, "AC:DB:FF"), device_id, device_id)
real_mac = ubinascii.hexlify(sta.config("mac"), ":").decode()

# The single receiver this network targets (your fixed receiver VMAC)
FINAL_VMAC = "AC:DB:02:01:01"

print("\n[BOOT] MKIV={} Role={} ID={} RawID={} Virtual={} Real={}\n".format(
    mkiv_flag, DEVICE_TYPE, device_id, raw_id, virtual_mac, real_mac
))


# =========================================================
# MKIV LED (GPIO27 NeoPixel) - MKIV only
# =========================================================
np = None
if mkiv_flag and neopixel is not None:
    try:
        np = neopixel.NeoPixel(machine.Pin(27, machine.Pin.OUT), 1)
    except Exception:
        np = None

def led_set(r, g, b):
    if np is None:
        return
    np[0] = (r, g, b)
    np.write()

def _role_color():
    if DEVICE_TYPE == "SENDER":
        return (0, 25, 0)
    if DEVICE_TYPE == "RELAY":
        return (0, 0, 25)
    if DEVICE_TYPE == "RECEIVER":
        return (25, 0, 25)
    if DEVICE_TYPE == "TELEMETRY":
        return (25, 15, 0)
    return (10, 10, 10)

_led_pulse_until = 0

def led_pulse(r, g, b, ms=60):
    global _led_pulse_until
    if np is None:
        return
    led_set(r, g, b)
    _led_pulse_until = _ticks_ms() + ms

def led_service():
    global _led_pulse_until
    if np is None:
        return
    if _led_pulse_until and _ticks_diff(_ticks_ms(), _led_pulse_until) >= 0:
        _led_pulse_until = 0
        led_set(*_role_color())

# steady color
led_set(*_role_color())


# =========================================================
# Packet formats + msg types
# =========================================================
PACKET_FORMAT   = ">16sBBHHH"   # dest_vmac(16), sid(u8), type(u8), ramp(u16), motion(u16), seq(u16)
PACKET_SIZE     = struct.calcsize(PACKET_FORMAT)

IDENTITY_FORMAT = "16s6s"       # vmac(16), realmac(6)
IDENTITY_SIZE   = struct.calcsize(IDENTITY_FORMAT)

MSG_DATA = 0xA1
MSG_HB   = 0xB1
MSG_PING = 0xC1
MSG_PONG = 0xC2

def make_identity_packet(vmac_str: str, rmac: bytes) -> bytes:
    return struct.pack(IDENTITY_FORMAT, _pad16(vmac_str.encode()), rmac)

def parse_identity_packet(msg: bytes):
    vmac_bytes, rmac = struct.unpack(IDENTITY_FORMAT, msg)
    return vmac_bytes.decode().strip("\x00"), rmac


# =========================================================
# SENDER
# =========================================================
def run_sender():
    # NOTE: ensure these pins are correct for your sender wiring
    RAMP_UP_PIN   = machine.Pin(33, machine.Pin.IN, machine.Pin.PULL_DOWN)
    RAMP_DOWN_PIN = machine.Pin(25, machine.Pin.IN, machine.Pin.PULL_DOWN)
    SIM_HOME_PIN  = machine.Pin(26, machine.Pin.IN, machine.Pin.PULL_DOWN)

    def get_ramp_state():
        ru = RAMP_UP_PIN.value()
        rd = RAMP_DOWN_PIN.value()
        if ru == 1 and rd == 1:
            return 0
        elif ru == 0:
            return 1
        elif rd == 0:
            return 2
        return 0

    def get_motion_state():
        # Your existing semantics:
        # 2 = In Operation, 1 = Standby
        return 1 if SIM_HOME_PIN.value() == 0 else 2

    receiver_rmac = None
    seq_counter = 0

    dest_receiver_field = _pad16(FINAL_VMAC.encode())

    IDENTITY_BASE_MS  = 30000
    HEARTBEAT_BASE_MS = 12000

    next_identity  = _ticks_ms() + IDENTITY_BASE_MS + _jitter_ms(2500)
    next_heartbeat = _ticks_ms() + HEARTBEAT_BASE_MS + _jitter_ms(1500)

    prev_ramp = None
    prev_mot  = None

    def broadcast_identity():
        pkt = make_identity_packet(virtual_mac, sta.config("mac"))
        try:
            esp.send(broadcast_mac, pkt)
        except Exception:
            pass

    def send_to_receiver(msg_type: int, ramp_state: int, motion_state: int):
        nonlocal seq_counter
        pkt = struct.pack(
            PACKET_FORMAT,
            dest_receiver_field,
            device_id,
            msg_type,
            ramp_state,
            motion_state,
            seq_counter
        )
        seq_counter = (seq_counter + 1) & 0xFFFF

        dest = receiver_rmac if receiver_rmac else broadcast_mac
        try:
            ok = bool(esp.send(dest, pkt))
            led_pulse(25, 25, 25, 40) if ok else led_pulse(25, 0, 0, 120)
        except Exception:
            led_pulse(25, 0, 0, 120)

    def send_pong_to(peer_mac: bytes):
        nonlocal seq_counter
        ramp_state = get_ramp_state()
        mot_state  = get_motion_state()
        pkt = struct.pack(
            PACKET_FORMAT,
            dest_receiver_field,
            device_id,
            MSG_PONG,
            ramp_state,
            mot_state,
            seq_counter
        )
        seq_counter = (seq_counter + 1) & 0xFFFF
        try:
            try:
                esp.add_peer(peer_mac)
            except Exception:
                pass
            ok = bool(esp.send(peer_mac, pkt))
            led_pulse(0, 25, 25, 60) if ok else led_pulse(25, 0, 0, 120)
        except Exception:
            led_pulse(25, 0, 0, 120)

    def handle_incoming():
        nonlocal receiver_rmac
        while True:
            peer, msg = esp_recv_nb()   # ✅ PATCH: non-blocking
            if not msg:
                break

            ln = len(msg)

            # Learn receiver real MAC via identity broadcasts
            if ln == IDENTITY_SIZE:
                try:
                    vmac, rmac = parse_identity_packet(msg)
                    if vmac == FINAL_VMAC:
                        receiver_rmac = rmac
                        try:
                            esp.add_peer(receiver_rmac)
                        except Exception:
                            pass
                except Exception:
                    pass
                continue

            # Respond to pings addressed to this sender VMAC
            if ln == PACKET_SIZE:
                try:
                    dest_field, sid, msg_type, ramp, mot, seq = struct.unpack(PACKET_FORMAT, msg)
                    dest_vmac = dest_field.decode().strip("\x00")
                    if msg_type == MSG_PING and dest_vmac == virtual_mac:
                        send_pong_to(peer)
                except Exception:
                    pass

    # --- Optional enhancement: fast boot announce ---
    time.sleep_ms(_jitter_ms(400))
    broadcast_identity()

    boot_deadline = _ticks_ms() + 600
    while _ticks_diff(_ticks_ms(), boot_deadline) < 0:
        handle_incoming()
        led_service()
        time.sleep_ms(10)

    # Send HB + PONG immediately so receiver clears offline quickly
    send_to_receiver(MSG_HB,   get_ramp_state(), get_motion_state())
    send_to_receiver(MSG_PONG, get_ramp_state(), get_motion_state())
    # ----------------------------------------------

    while True:
        now = _ticks_ms()

        handle_incoming()

        if _ticks_diff(now, next_identity) >= 0:
            broadcast_identity()
            next_identity = now + IDENTITY_BASE_MS + _jitter_ms(3500)

        if _ticks_diff(now, next_heartbeat) >= 0:
            send_to_receiver(MSG_HB, get_ramp_state(), get_motion_state())
            next_heartbeat = now + HEARTBEAT_BASE_MS + _jitter_ms(2000)

        cur_ramp = get_ramp_state()
        cur_mot  = get_motion_state()
        if prev_ramp is None or cur_ramp != prev_ramp or cur_mot != prev_mot:
            send_to_receiver(MSG_DATA, cur_ramp, cur_mot)
            prev_ramp = cur_ramp
            prev_mot  = cur_mot

        led_service()
        time.sleep_ms(20)


# =========================================================
# RELAY (IRQ -> queue -> main loop)
# =========================================================
def run_relay():
    known_peers = {}  # vmac -> {"real_mac": bytes, "type": str, "hop": int}

    QSIZE = 64
    q_peer = [None] * QSIZE
    q_msg  = [None] * QSIZE
    q_head = 0
    q_tail = 0

    def q_put(peer, msg):
        nonlocal q_head, q_tail
        nxt = (q_head + 1) % QSIZE
        if nxt == q_tail:
            return False
        q_peer[q_head] = peer
        q_msg[q_head]  = msg
        q_head = nxt
        return True

    def q_get():
        nonlocal q_head, q_tail
        if q_tail == q_head:
            return None, None
        peer = q_peer[q_tail]
        msg  = q_msg[q_tail]
        q_peer[q_tail] = None
        q_msg[q_tail]  = None
        q_tail = (q_tail + 1) % QSIZE
        return peer, msg

    def process_identity(msg):
        try:
            vmac, rmac = parse_identity_packet(msg)
        except Exception:
            return

        if vmac not in known_peers:
            known_peers[vmac] = {"real_mac": rmac, "type": "UNKNOWN", "hop": 999}
            try:
                esp.add_peer(rmac)
            except Exception:
                pass

        if vmac == FINAL_VMAC:
            known_peers[vmac]["type"] = "RECEIVER"
            known_peers[vmac]["hop"] = 0
        elif vmac.startswith("AC:DB:01:"):
            known_peers[vmac]["type"] = "RELAY"
        elif vmac.startswith("AC:DB:00:"):
            known_peers[vmac]["type"] = "SENDER"

    def forward(dest_vmac: str, packet: bytes) -> bool:
        # Prefer direct to receiver if known
        if dest_vmac == FINAL_VMAC and dest_vmac in known_peers:
            rmac = known_peers[dest_vmac]["real_mac"]
            try:
                return bool(esp.send(rmac, packet))
            except Exception:
                return False

        # Otherwise forward to best relay if known, else broadcast
        best_relay = None
        best_hop = 999
        for vmac, info in known_peers.items():
            if info.get("type") == "RELAY" and info.get("hop", 999) < best_hop:
                best_hop = info["hop"]
                best_relay = info["real_mac"]

        try:
            if best_relay:
                return bool(esp.send(best_relay, packet))
            return bool(esp.send(broadcast_mac, packet))
        except Exception:
            return False

    def on_data_recv(*_):
        # ✅ PATCH: use non-blocking recv inside IRQ so it cannot hang
        while True:
            peer, msg = esp_recv_nb()
            if not msg:
                break
            q_put(peer, msg)

    esp.irq(on_data_recv)

    print("[RELAY] Ready (queued IRQ forwarding)")
    led_set(*_role_color())

    while True:
        for _ in range(28):
            peer, msg = q_get()
            if not msg:
                break

            ln = len(msg)
            if ln == IDENTITY_SIZE:
                process_identity(msg)
                continue

            if ln == PACKET_SIZE:
                try:
                    dest_field, sid, msg_type, ramp, mot, seq = struct.unpack(PACKET_FORMAT, msg)
                    dest_vmac = dest_field.decode().strip("\x00")
                    ok = forward(dest_vmac, msg)
                    led_pulse(25, 25, 25, 30) if ok else led_pulse(25, 0, 0, 120)
                except Exception:
                    pass

        led_service()
        time.sleep_ms(10)


# =========================================================
# RECEIVER (serial CSV output + ping/pong verify)
# =========================================================
def run_receiver():
    # Serial protocol:
    #   R,1
    #   O,<sid>,<0|1>
    #   S,<sid>,<motion>,<ramp>,<seq>

    EMIT_RECEIVER_ALIVE = True
    RECEIVER_ALIVE_MS = 5000

    HEARTBEAT_TIMEOUT_MS = 90000
    PING_WAIT_MS         = 800
    PING_RETRIES         = 2

    IDENTITY_BASE_MS = 30000

    now = _ticks_ms()
    next_identity = now + IDENTITY_BASE_MS + _jitter_ms(2500)
    next_alive = now + RECEIVER_ALIVE_MS

    senders = {}           # sid -> record
    sender_mac_by_id = {}  # sid -> real mac

    def parse_id_from_vmac(vmac: str):
        try:
            parts = vmac.split(":")
            return int(parts[-1], 16) if len(parts) >= 2 else None
        except Exception:
            return None

    def broadcast_receiver_identity():
        pkt = make_identity_packet(virtual_mac, sta.config("mac"))
        try:
            esp.send(broadcast_mac, pkt)
        except Exception:
            pass

    def emit_state(sid: int, motion: int, ramp: int, seq: int):
        print("S,{},{},{},{}".format(sid, motion, ramp, seq))

    def emit_online(sid: int, online: int):
        print("O,{},{}".format(sid, online))

    def emit_receiver_alive():
        print("R,1")

    def send_ping(sid: int, sender_rmac: bytes):
        sender_vmac = "AC:DB:00:{:02X}:{:02X}".format(sid, sid)
        dest_field = _pad16(sender_vmac.encode())
        pkt = struct.pack(PACKET_FORMAT, dest_field, device_id, MSG_PING, 0, 0, 0)
        try:
            try:
                esp.add_peer(sender_rmac)
            except Exception:
                pass
            esp.send(sender_rmac, pkt)
        except Exception:
            pass

    def try_consume_pong_for(target_sid: int):
        # ✅ PATCH: non-blocking polling for pong
        while True:
            peer, msg = esp_recv_nb()
            if not msg:
                return (False, None, None, None)

            if len(msg) != PACKET_SIZE:
                continue

            try:
                dest_field, sid, msg_type, ramp_state, motion_state, seq = struct.unpack(PACKET_FORMAT, msg)
                if msg_type == MSG_PONG and sid == target_sid:
                    return (True, ramp_state, motion_state, seq)
            except Exception:
                pass

    # Boot identity broadcast
    time.sleep_ms(_jitter_ms(400))
    broadcast_receiver_identity()
    led_set(*_role_color())

    # (Optional) extra visible heartbeat at boot
    if EMIT_RECEIVER_ALIVE:
        print("R,1")

    while True:
        now = _ticks_ms()

        if EMIT_RECEIVER_ALIVE and _ticks_diff(now, next_alive) >= 0:
            emit_receiver_alive()
            next_alive = now + RECEIVER_ALIVE_MS

        if _ticks_diff(now, next_identity) >= 0:
            broadcast_receiver_identity()
            next_identity = now + IDENTITY_BASE_MS + _jitter_ms(3500)

        # Drain RX (✅ PATCH: non-blocking recv)
        while True:
            peer, msg = esp_recv_nb()
            if not msg:
                break

            ln = len(msg)

            if ln == IDENTITY_SIZE:
                try:
                    vmac, rmac = parse_identity_packet(msg)
                    sid = parse_id_from_vmac(vmac)
                    if sid is not None and vmac.startswith("AC:DB:00:"):
                        sender_mac_by_id[sid] = rmac
                        try:
                            esp.add_peer(rmac)
                        except Exception:
                            pass
                except Exception:
                    pass
                continue

            if ln == PACKET_SIZE:
                try:
                    dest_field, sid, msg_type, ramp_state, motion_state, seq = struct.unpack(PACKET_FORMAT, msg)
                    dest_vmac = dest_field.decode().strip("\x00")
                    if dest_vmac != virtual_mac:
                        continue

                    rec = senders.get(sid)
                    if not rec:
                        rec = {
                            "last_seen": now,
                            "last_seq": seq,
                            "ramp": ramp_state,
                            "motion": motion_state,
                            "offline": False,
                            "miss_seq": 0,
                        }
                        senders[sid] = rec
                        emit_online(sid, 1)
                        emit_state(sid, motion_state, ramp_state, seq)

                    gap = (seq - rec["last_seq"]) & 0xFFFF
                    if gap > 1:
                        rec["miss_seq"] += (gap - 1)
                    rec["last_seq"] = seq

                    rec["last_seen"] = now

                    if rec["offline"]:
                        rec["offline"] = False
                        emit_online(sid, 1)

                    changed = (ramp_state != rec["ramp"]) or (motion_state != rec["motion"])
                    rec["ramp"] = ramp_state
                    rec["motion"] = motion_state

                    # Emit state only when changed OR on explicit DATA frames
                    if changed or msg_type == MSG_DATA:
                        emit_state(sid, motion_state, ramp_state, seq)

                    led_pulse(25, 25, 25, 25)

                except Exception:
                    pass

        # Timeout verify (ping/pong)
        for sid, rec in senders.items():
            if rec["offline"]:
                continue

            if _ticks_diff(now, rec["last_seen"]) > HEARTBEAT_TIMEOUT_MS:
                rmac = sender_mac_by_id.get(sid)
                if not rmac:
                    rec["offline"] = True
                    emit_online(sid, 0)
                    led_pulse(25, 0, 0, 120)
                    continue

                alive = False
                for _ in range(PING_RETRIES):
                    send_ping(sid, rmac)
                    deadline = _ticks_ms() + PING_WAIT_MS

                    while _ticks_diff(_ticks_ms(), deadline) < 0:
                        ok, ramp, mot, seq = try_consume_pong_for(sid)
                        if ok:
                            rec["last_seen"] = _ticks_ms()
                            if ramp is not None and mot is not None:
                                changed = (ramp != rec["ramp"]) or (mot != rec["motion"])
                                rec["ramp"] = ramp
                                rec["motion"] = mot
                                if changed:
                                    emit_state(sid, mot, ramp, seq if seq is not None else rec["last_seq"])
                            alive = True
                            break
                        time.sleep_ms(5)

                    if alive:
                        break

                if not alive:
                    rec["offline"] = True
                    emit_online(sid, 0)
                    led_pulse(25, 0, 0, 120)

        led_service()
        time.sleep_ms(5)


# =========================================================
# Dispatch
# =========================================================
if DEVICE_TYPE == "SENDER":
    run_sender()
elif DEVICE_TYPE == "RELAY":
    run_relay()
elif DEVICE_TYPE == "RECEIVER":
    run_receiver()
else:
    print("[ERROR] Unknown role. Exiting.")
    led_set(25, 0, 0)