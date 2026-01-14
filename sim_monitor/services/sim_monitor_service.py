#!/usr/bin/env python3
"""
Sim Monitor Service (Pi5)
-------------------------
Reads ESP32 Receiver serial output and writes to SQLite.

Expected receiver frames (CSV):
  R,1
  O,<sid>,<0|1>     (accepts O or 0)
  S,<sid>,<motion>,<ramp>,<seq>

Receiver ONLINE logic:
  - If PORT_OPEN_COUNTS_AS_ONLINE: online immediately on port open
  - OR any serial bytes received (even noise) keeps it online

Receiver OFFLINE logic:
  - No serial bytes received for RECEIVER_TIMEOUT seconds
  - OR serial exception / disconnect

Auto-reconnect:
  - On serial errors, close and reopen after RECONNECT_DELAY_SEC
"""

import time, re, sys, pathlib

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
ONLINE_RE = re.compile(r"^[O0],(\d+),(0|1)$")                  # O or 0
STATE_RE  = re.compile(r"^S,(\d+),(\d+),(\d+),(\d+)$")         # sid,motion,ramp,seq


# -----------------------------
# Config
# -----------------------------
BAUD = 115200
PREFERRED_PORT = "/dev/ttyUSB0"     # "" to force autoscan
SERIAL_TIMEOUT = 1.0

RECEIVER_TIMEOUT = 20.0            # seconds of *no serial bytes* => receiver offline
SENDER_TIMEOUT   = 180.0           # seconds since last_update_ts => sender offline

PORT_OPEN_COUNTS_AS_ONLINE = True
RECONNECT_DELAY_SEC = 2.0

# Optional helper for some USB serial adapters
FORCE_PORT_DTR_RTS = False


# -----------------------------
# DB helpers
# -----------------------------
def update_receiver_status(online: bool, *, ts: float | None = None):
    now = int(ts if ts is not None else time.time())
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE system_status SET receiver_online=?, last_seen=? WHERE id=1",
        (1 if online else 0, now)
    )
    conn.commit()
    conn.close()


def update_sender(sim_id: int, motion: int, ramp: int, *, ts: float | None = None):
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


def set_sender_online_flag(sim_id: int, online: bool, *, ts: float | None = None):
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


def handle_motion(sim_id: int, motion_state: int, *, ts: float | None = None):
    """
    Motion sessions start when motion_state == 2 (In Operation / red).
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
    row = cur.fetchone()
    in_motion = row is not None

    now = int(ts if ts is not None else time.time())

    if motion_state == 2 and not in_motion:
        cur.execute(
            "INSERT OR REPLACE INTO active_motion (sim_id, start_ts) VALUES (?, ?)",
            (sim_id, now)
        )

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
        if now - last_ts > int(SENDER_TIMEOUT):
            cur.execute("UPDATE simulators SET online=0 WHERE sim_id=?", (sim_id,))

    conn.commit()
    conn.close()


# -----------------------------
# Serial open helpers
# -----------------------------
def open_serial_port():
    if serial is None:
        raise RuntimeError("pyserial not installed")

    def _open(dev: str):
        s = serial.Serial(dev, BAUD, timeout=SERIAL_TIMEOUT)
        if FORCE_PORT_DTR_RTS:
            try:
                s.dtr = True
                s.rts = True
            except Exception:
                pass
        return s

    if PREFERRED_PORT:
        try:
            return _open(PREFERRED_PORT)
        except Exception:
            pass

    for p in serial.tools.list_ports.comports():
        try:
            return _open(p.device)
        except Exception:
            continue

    raise RuntimeError("No serial ports available")


# -----------------------------
# Main loop with auto-reconnect
# -----------------------------
def run_service():
    init_db()
    update_receiver_status(False)

    while True:
        ser = None
        receiver_online = False
        last_serial_activity_ts = 0.0
        last_timeout_check = 0.0

        try:
            ser = open_serial_port()
            now = time.time()
            print(f"[SimMonitorService] Opened serial port {ser.port}")

            try:
                ser.reset_input_buffer()
            except Exception:
                pass

            if PORT_OPEN_COUNTS_AS_ONLINE:
                receiver_online = True
                last_serial_activity_ts = now
                update_receiver_status(True, ts=now)

            while True:
                raw = ser.readline()
                now = time.time()

                # periodic sender timeout cleanup
                if now - last_timeout_check > 5.0:
                    check_sender_timeouts()
                    last_timeout_check = now

                if not raw:
                    if receiver_online and last_serial_activity_ts and (now - last_serial_activity_ts > RECEIVER_TIMEOUT):
                        receiver_online = False
                        update_receiver_status(False, ts=now)
                        print(f"[SimMonitorService] Receiver OFFLINE (no serial bytes for {RECEIVER_TIMEOUT}s)")
                    continue

                # any bytes => activity
                last_serial_activity_ts = now
                if not receiver_online:
                    receiver_online = True
                    print("[SimMonitorService] Receiver ONLINE (serial activity resumed)")
                update_receiver_status(True, ts=now)

                line = raw.decode(errors="ignore").strip()
                if not line:
                    continue

                mR = RECV_RE.match(line)
                mO = ONLINE_RE.match(line)
                mS = STATE_RE.match(line)

                if not (mR or mO or mS):
                    continue

                if mR:
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
                    update_sender(sid, motion, ramp, ts=now)
                    handle_motion(sid, motion, ts=now)

        except KeyboardInterrupt:
            print("[SimMonitorService] Stopped by user")
            break

        except Exception as e:
            now = time.time()
            print(f"[SimMonitorService] Serial error: {e}")
            update_receiver_status(False, ts=now)

        finally:
            try:
                if ser:
                    ser.close()
            except Exception:
                pass

        time.sleep(RECONNECT_DELAY_SEC)


if __name__ == "__main__":
    run_service()