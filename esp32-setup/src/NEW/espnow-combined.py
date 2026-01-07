# simnode_espnow_unified_mkiv_legacy.py
# ------------------------------------------------------------
# Unified ESP-NOW firmware for SENDER / RELAY / RECEIVER
#
# Includes:
#   • Queue-based relay (no heavy work in IRQ)
#   • Receiver drains RX queue (no 50ms blind spots)
#   • Heartbeat jitter + faster heartbeat
#   • Real-MAC discovery + opportunistic unicast
#   • ESP-NOW application-level PING / PONG reachability verification
#   • Optional enhancement: Sender boot announces (IDENTITY + HB + PONG)
#
# MKIV / Legacy split:
#   • MKIV detect: if ONLY GPIO19 is pulled HIGH (GPIO18=0, GPIO14=0) => MKIV
#   • MKIV role: uses GPIO18/GPIO14 as 2-bit role selector
#   • MKIV ID logic (current): raw_id = (17<<3)|(5<<2)|(4<<1)|16 ; device_id = raw_id ^ 0x0F
#   • MKIV LED: single NeoPixel/WS2812 data-in on GPIO27
#
#   • Legacy boards: NO LED support
#   • Legacy role logic (from espnow-combined.py): role uses GPIO18/GPIO19 (2-bit)
#   • Legacy ID logic (from espnow-combined.py):
#         old_raw_id = (GPIO4<<0) | (GPIO16<<1) | (GPIO17<<2) | (GPIO5<<3)
#         device_id = old_raw_id   (no XOR)
#
# Serial output compatibility (Qt serial handler):
#   • Receiver prints:
#       [DATA] Received from Sender ID X: RampState=Y, MotionState=Z, Seq=N
#       [HEARTBEAT] ... (throttled)
# ------------------------------------------------------------

import network
import espnow
import machine
import ubinascii
import time
import struct
import urandom

# NeoPixel (only used on MKIV)
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

# =========================================================
# Wi-Fi / ESP-NOW init
# =========================================================
sta = network.WLAN(network.STA_IF)
sta.active(True)

try:
    sta.config(pm=0)  # reduce Wi-Fi power-save latency if supported
except Exception:
    pass

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
# MKIV detection + role decode
# =========================================================
# Role pins present on both, but semantics differ by board.
PIN19 = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_DOWN)
PIN18 = machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_DOWN)
PIN14 = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_DOWN)

time.sleep_ms(50)

# MKIV detect: ONLY GPIO19 high, and GPIO18/GPIO14 low.
mkiv_flag = (PIN19.value() == 1 and PIN18.value() == 0 and PIN14.value() == 0)

roles = {0: "SENDER", 1: "RELAY", 2: "RECEIVER", 3: "TELEMETRY"}

if mkiv_flag:
    # MKIV: role is 2-bit on (18,14)
    role_value = (PIN18.value() << 1) | PIN14.value()
else:
    # Legacy: role is 2-bit on (18,19) per espnow-combined.py
    role_value = (PIN18.value() << 1) | PIN19.value()

DEVICE_TYPE = roles.get(role_value, "UNKNOWN")

# =========================================================
# Device ID decode (MKIV vs Legacy)
# =========================================================
if mkiv_flag:
    # MKIV "current logic" (your A/B/C/D):
    # A=GPIO17 (bit3), B=GPIO5 (bit2), C=GPIO4 (bit1), D=GPIO16 (bit0)
    A = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
    B = machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    C = machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    D = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)

    raw_id = ((A.value() << 3) | (B.value() << 2) | (C.value() << 1) | D.value())
    device_id = raw_id ^ 0x0F  # invert
else:
    # Legacy logic from espnow-combined.py:
    # id_pins = [GPIO4, GPIO16, GPIO17, GPIO5] with enumerate bit positions 0..3
    P4  = machine.Pin(4,  machine.Pin.IN, machine.Pin.PULL_DOWN)
    P16 = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)
    P17 = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
    P5  = machine.Pin(5,  machine.Pin.IN, machine.Pin.PULL_DOWN)

    device_id = (P4.value() << 0) | (P16.value() << 1) | (P17.value() << 2) | (P5.value() << 3)

# =========================================================
# Virtual MAC scheme
# =========================================================
mac_prefix = {
    "SENDER":   "AC:DB:00",
    "RELAY":    "AC:DB:01",
    "RECEIVER": "AC:DB:02",
    "TELEMETRY":"AC:DB:03",
}

virtual_mac = f"{mac_prefix.get(DEVICE_TYPE, 'AC:DB:FF')}:{device_id:02X}:{device_id:02X}"
real_mac = ubinascii.hexlify(sta.config("mac"), ":").decode()

FINAL_VMAC = "AC:DB:02:01:01"

print(f"\n[BOOT] MKIV={mkiv_flag} Role={DEVICE_TYPE} ID={device_id} Virtual={virtual_mac} Real={real_mac}\n")

# =========================================================
# MKIV LED (NeoPixel on GPIO27) - MKIV only
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
        return (0, 25, 0)     # green
    if DEVICE_TYPE == "RELAY":
        return (0, 0, 25)     # blue
    if DEVICE_TYPE == "RECEIVER":
        return (25, 0, 25)    # purple
    if DEVICE_TYPE == "TELEMETRY":
        return (25, 15, 0)    # amber
    return (10, 10, 10)       # gray

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

# steady role color
led_set(*_role_color())

# =========================================================
# Packet formats + msg types
# =========================================================
PACKET_FORMAT   = ">16sBBHHH"
PACKET_SIZE     = struct.calcsize(PACKET_FORMAT)

IDENTITY_FORMAT = "16s6s"
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
        pkt = struct.pack(PACKET_FORMAT, dest_receiver_field, device_id, msg_type,
                          ramp_state, motion_state, seq_counter)
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
        pkt = struct.pack(PACKET_FORMAT, dest_receiver_field, device_id, MSG_PONG,
                          ramp_state, mot_state, seq_counter)
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
            peer, msg = esp.recv()
            if not msg:
                break

            ln = len(msg)

            # Learn receiver real MAC from identity broadcasts
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

            # Answer pings addressed to this sender VMAC
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

    # Immediately send HB + PONG so receiver clears offline quickly
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
# RELAY (queued IRQ)
# =========================================================
def run_relay():
    known_peers = {}  # vmac -> {"real_mac": bytes, "type": str, "hop": int}

    QSIZE = 64
    q_peer = [None] * QSIZE
    q_msg  = [None] * QSIZE
    q_head = 0
    q_tail = 0
    q_drop = 0

    def q_put(peer, msg):
        nonlocal q_head, q_tail, q_drop
        nxt = (q_head + 1) % QSIZE
        if nxt == q_tail:
            q_drop += 1
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
        if dest_vmac == FINAL_VMAC and dest_vmac in known_peers:
            rmac = known_peers[dest_vmac]["real_mac"]
            try:
                return bool(esp.send(rmac, packet))
            except Exception:
                return False

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
        while True:
            peer, msg = esp.recv()
            if not msg:
                break
            q_put(peer, msg)

    esp.irq(on_data_recv)

    print("[RELAY] Ready (IRQ queued, main-loop forwarding)")
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
# RECEIVER (drain loop + PING/PONG verify)
# =========================================================
def run_receiver():
    # Qt serial handler compatibility:
    PRINT_DATA_ALWAYS = True
    PRINT_HEARTBEATS  = True
    HB_PRINT_MIN_MS   = 5000  # per-sender heartbeat print throttle

    last_hb_print = {}  # sid -> ticks_ms

    senders = {}            # sid -> dict
    sender_mac_by_id = {}   # sid -> real MAC (learned from identity)

    HEARTBEAT_TIMEOUT_MS = 60000  # suspect offline after 60s no traffic
    PING_WAIT_MS         = 800
    PING_RETRIES         = 2

    IDENTITY_BASE_MS = 30000
    next_identity = _ticks_ms() + IDENTITY_BASE_MS + _jitter_ms(2500)

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

    def send_ping(sid: int, sender_rmac: bytes):
        sender_vmac = f"AC:DB:00:{sid:02X}:{sid:02X}"
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
        while True:
            peer, msg = esp.recv()
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

    time.sleep_ms(_jitter_ms(400))
    broadcast_receiver_identity()
    led_set(*_role_color())

    while True:
        now = _ticks_ms()

        if _ticks_diff(now, next_identity) >= 0:
            broadcast_receiver_identity()
            next_identity = now + IDENTITY_BASE_MS + _jitter_ms(3500)

        # Drain RX queue
        while True:
            peer, msg = esp.recv()
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
                            "hb": 0,
                            "data": 0,
                            "miss_seq": 0,
                            "offline": False,
                        }
                        senders[sid] = rec

                    gap = (seq - rec["last_seq"]) & 0xFFFF
                    if gap > 1:
                        rec["miss_seq"] += (gap - 1)

                    rec["last_seq"] = seq
                    rec["last_seen"] = now
                    rec["ramp"] = ramp_state
                    rec["motion"] = motion_state

                    if msg_type == MSG_HB:
                        rec["hb"] += 1
                        if PRINT_HEARTBEATS:
                            lastp = last_hb_print.get(sid, 0)
                            if _ticks_diff(now, lastp) > HB_PRINT_MIN_MS:
                                last_hb_print[sid] = now
                                print(f"[HEARTBEAT] Received from Sender ID {sid}: "
                                      f"RampState={ramp_state}, MotionState={motion_state}, Seq={seq}")

                    elif msg_type == MSG_DATA:
                        rec["data"] += 1
                        if PRINT_DATA_ALWAYS:
                            print(f"[DATA] Received from Sender ID {sid}: "
                                  f"RampState={ramp_state}, MotionState={motion_state}, Seq={seq}")

                    elif msg_type == MSG_PONG:
                        # do not print in production
                        pass

                    if rec["offline"]:
                        rec["offline"] = False

                    led_pulse(25, 25, 25, 25)
                except Exception:
                    pass

        # Active verification on timeout
        for sid, rec in senders.items():
            if rec["offline"]:
                continue

            if _ticks_diff(now, rec["last_seen"]) > HEARTBEAT_TIMEOUT_MS:
                rmac = sender_mac_by_id.get(sid)
                if not rmac:
                    rec["offline"] = True
                    continue

                alive = False
                for _ in range(PING_RETRIES):
                    send_ping(sid, rmac)
                    deadline = _ticks_ms() + PING_WAIT_MS

                    while _ticks_diff(_ticks_ms(), deadline) < 0:
                        ok, ramp, mot, seq = try_consume_pong_for(sid)
                        if ok:
                            rec["last_seen"] = _ticks_ms()
                            rec["ramp"] = ramp
                            rec["motion"] = mot
                            alive = True
                            break
                        time.sleep_ms(5)

                    if alive:
                        break

                if not alive:
                    rec["offline"] = True
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