#!/usr/bin/env python3
"""
Sim Monitor Service (Pi5)
-------------------------
Reads ESP32 Receiver serial output and writes to SQLite.

Expected receiver frames (CSV):
  R,1
  O,<sid>,<0|1>
  S,<sid>,<motion>,<ramp>,<seq>

KEY IMPROVEMENTS:
  • Receiver ONLINE if:
      - serial port opens successfully (optional, enabled)
      - AND/OR any serial activity is observed
  • Receiver OFFLINE only if:
      - no serial activity for RECEIVER_TIMEOUT seconds
      - OR serial exceptions / disconnects
  • Auto-reconnect loop on serial failures
  • Robust: accepts O or 0 prefix for online frames (O vs zero)
"""

import time, re, sys, pathlib

# Ensure project root is on sys.path
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.db import get_conn, init_db

try:
    import serial, serial.tools.list_ports
except ImportError:
    serial = None


# -----------------------------
# Receiver CSV protocol
# -----------------------------
RECV_RE   = re.compile(r"^R,1$")
# Accept O or 0 (letter O vs zero) just in case
ONLINE_RE = re.compile(r"^[O0],(\d+),(0|1)$")
STATE_RE  = re.compile(r"^S,(\d+),(\d+),(\d+),(\d+)$")  # sid,motion,ramp,seq


# -----------------------------
# Config
# -----------------------------
BAUD = 115200
PREFERRED_PORT = "/dev/ttyUSB0"   # set "" to force autoscan
SERIAL_TIMEOUT = 1.0

# Receiver considered offline if NO SERIAL ACTIVITY for this time (seconds)
RECEIVER_TIMEOUT = 20

# Sender considered offline if DB last_update_ts older than this (seconds)
SENDER_TIMEOUT = 180

# If True: port open => receiver online immediately (even if receiver doesn't print R,1)
PORT_OPEN_COUNTS_AS_ONLINE = True

# Auto-reconnect delay when serial fails
RECONNECT_DELAY_SEC = 2.0


# -----------------------------
# DB helpers
# -----------------------------
def update_receiver_status(online: bool, *, ts: int | None = None):
    now = int(ts if ts is not None else time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE system_status SET receiver_online=?, last_seen=? WHERE id=1",
        (1 if online else 0, now)
    )
    conn.commit()
    conn.close()


def update_sender(sim_id: int, motion: int, ramp: int, *, ts: int | None = None):
    now = int(ts if ts is not None else time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO simulators (sim_id, motion_state, ramp_state, last_update_ts, online)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(sim_id) DO UPDATE SET
            motion_state=excluded.motion_state,
            ramp_state=excluded.ramp_state,
            last_update_ts=excluded.last_update_ts,
            online=1
    """, (sim_id, motion, ramp, now))
    conn.commit()
    conn.close()


def set_sender_online_flag(sim_id: int, online: bool, *, ts: int | None = None):
    now = int(ts if ts is not None else time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO simulators (sim_id, last_update_ts, online)
        VALUES (?, ?, ?)
        ON CONFLICT(sim_id) DO UPDATE SET
            last_update_ts=excluded.last_update_ts,
            online=excluded.online
    """, (sim_id, now, 1 if online else 0))
    conn.commit()
    conn.close()


def handle_motion(sim_id: int, motion_state: int, *, ts: int | None = None):
    """
    Your GUI treats motion_state == 2 as 'In Operation' (red).
    So motion sessions should start when motion_state == 2.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
    row = cur.fetchone()
    in_motion = row is not None

    now = int(ts if ts is not None else time.time())

    # Motion starts
    if motion_state == 2 and not in_motion:
        cur.execute(
            "INSERT OR REPLACE INTO active_motion (sim_id, start_ts) VALUES (?, ?)",
            (sim_id, now)
        )

    # Motion ends
    if motion_state != 2 and in_motion:
        start = row[0]
        duration = now - start
        cur.execute("""
            INSERT INTO motion_sessions (sim_id, start_ts, end_ts, duration_sec)
            VALUES (?, ?, ?, ?)
        """, (sim_id, start, now, duration))
        cur.execute("DELETE FROM active_motion WHERE sim_id=?", (sim_id,))

    conn.commit()
    conn.close()


def check_sender_timeouts():
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT sim_id, last_update_ts FROM simulators")
    for sim_id, last_ts in cur.fetchall():
        if last_ts is None:
            continue
        if now - last_ts > SENDER_TIMEOUT:
            cur.execute("UPDATE simulators SET online=0 WHERE sim_id=?", (sim_id,))

    conn.commit()
    conn.close()


# -----------------------------
# Serial open helpers
# -----------------------------
def open_serial_port():
    if serial is None:
        raise RuntimeError("pyserial not installed")

    # Try preferred port first
    if PREFERRED_PORT:
        try:
            return serial.Serial(PREFERRED_PORT, BAUD, timeout=SERIAL_TIMEOUT)
        except Exception:
            pass

    # Auto-scan ports
    for p in serial.tools.list_ports.comports():
        try:
            return serial.Serial(p.device, BAUD, timeout=SERIAL_TIMEOUT)
        except Exception:
            continue

    raise RuntimeError("No serial ports available")


# -----------------------------
# Main loop with auto-reconnect
# -----------------------------
def run_service():
    init_db()

    # Always start "offline" until we open port / see activity
    update_receiver_status(False)

    while True:
        ser = None
        receiver_online = False
        last_serial_activity_ts = 0
        last_timeout_check = 0

        try:
            ser = open_serial_port()
            now = int(time.time())
            print(f"[SimMonitorService] Opened serial port {ser.port}")

            # Clear junk
            try:
                ser.reset_input_buffer()
            except Exception:
                pass

            # Port-open => online (optional)
            if PORT_OPEN_COUNTS_AS_ONLINE:
                receiver_online = True
                last_serial_activity_ts = now
                update_receiver_status(True, ts=now)

            while True:
                raw = ser.readline()
                now = int(time.time())

                # Periodic sender timeout cleanup
                if now - last_timeout_check > 5:
                    check_sender_timeouts()
                    last_timeout_check = now

                if not raw:
                    # No bytes this cycle; offline only if NO serial activity for long enough
                    if receiver_online and last_serial_activity_ts and (now - last_serial_activity_ts > RECEIVER_TIMEOUT):
                        receiver_online = False
                        update_receiver_status(False, ts=now)
                    continue

                # We saw bytes (any activity)
                last_serial_activity_ts = now

                # Any activity can revive online state
                if not receiver_online:
                    receiver_online = True
                update_receiver_status(True, ts=now)

                # Decode line
                line = raw.decode(errors="ignore").strip()
                if not line:
                    continue

                # Parse frames
                mR = RECV_RE.match(line)
                mO = ONLINE_RE.match(line)
                mS = STATE_RE.match(line)

                if not (mR or mO or mS):
                    # noise, but counts as activity already
                    continue

                if mR:
                    # keepalive only
                    continue

                if mO:
                    sid = int(mO.group(1))
                    online = int(mO.group(2))
                    set_sender_online_flag(sid, bool(online), ts=now)
                    continue

                if mS:
                    sid = int(mS.group(1))
                    motion = int(mS.group(2))
                    ramp = int(mS.group(3))
                    # seq = int(mS.group(4))  # available if you want logging later

                    update_sender(sid, motion, ramp, ts=now)
                    handle_motion(sid, motion, ts=now)

        except KeyboardInterrupt:
            print("[SimMonitorService] Stopped by user")
            break

        except Exception as e:
            # Serial failure => receiver offline + reconnect
            now = int(time.time())
            print(f"[SimMonitorService] Serial error: {e}")
            update_receiver_status(False, ts=now)

        finally:
            try:
                if ser:
                    ser.close()
            except Exception:
                pass

        # Reconnect delay
        time.sleep(RECONNECT_DELAY_SEC)


if __name__ == "__main__":
    run_service()