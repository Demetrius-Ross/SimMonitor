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

# ============================================================
# New ESP32 receiver CSV frames:
#   R,1
#   O,<sid>,<0|1>
#   S,<sid>,<motion>,<ramp>,<seq>
# ============================================================
R_RE = re.compile(r"^R,1$")
O_RE = re.compile(r"^O,(\d+),(0|1)$")
S_RE = re.compile(r"^S,(\d+),(\d+),(\d+),(\d+)$")

# Timeouts
SENDER_TIMEOUT   = 180    # seconds before marking sender offline
RECEIVER_TIMEOUT = 20     # seconds of no valid frames => receiver offline

BAUD = 115200
PREFERRED_PORT = "/dev/ttyUSB0"  # set "" to auto-scan


# ============================================================
# DB helpers (MATCH YOUR SCHEMA EXACTLY)
# ============================================================
def update_receiver_status(online: bool):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE system_status SET receiver_online=?, last_seen=? WHERE id=1",
        (1 if online else 0, int(time.time()))
    )
    conn.commit()
    conn.close()


def touch_sim(cur, sim_id: int, now_ts: int):
    cur.execute("""
        INSERT OR IGNORE INTO simulators (sim_id, motion_state, ramp_state, last_update_ts, online)
        VALUES (?, 0, 0, ?, 0)
    """, (sim_id, now_ts))


def set_sender_online(sim_id: int, online: bool):
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()

    touch_sim(cur, sim_id, now)

    cur.execute("""
        UPDATE simulators
        SET online=?, last_update_ts=?
        WHERE sim_id=?
    """, (1 if online else 0, now, sim_id))

    conn.commit()
    conn.close()


def update_sender_state(sim_id: int, motion: int, ramp: int):
    """
    Update simulators row (online=1) + last_update_ts.
    """
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()

    touch_sim(cur, sim_id, now)

    cur.execute("""
        UPDATE simulators
        SET motion_state=?, ramp_state=?, last_update_ts=?, online=1
        WHERE sim_id=?
    """, (motion, ramp, now, sim_id))

    conn.commit()
    conn.close()


def handle_motion(sim_id: int, motion_state: int):
    """
    Convention used by our updated system:
      motion_state == 1  => IN MOTION
      motion_state != 1  => NOT moving (home)
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
    row = cur.fetchone()
    in_motion = row is not None
    now = int(time.time())

    # Motion starts
    if motion_state == 1 and not in_motion:
        cur.execute(
            "INSERT OR REPLACE INTO active_motion (sim_id, start_ts) VALUES (?, ?)",
            (sim_id, now)
        )

    # Motion ends
    if motion_state != 1 and in_motion:
        start = int(row[0])
        dur = max(0, now - start)

        cur.execute("""
            INSERT INTO motion_sessions (sim_id, start_ts, end_ts, duration_sec)
            VALUES (?, ?, ?, ?)
        """, (sim_id, start, now, dur))

        cur.execute("DELETE FROM active_motion WHERE sim_id=?", (sim_id,))

    conn.commit()
    conn.close()


def check_sender_timeouts():
    """
    Marks senders offline if they haven't updated recently.
    Also closes any active motion session to avoid "stuck in motion".
    """
    now = int(time.time())
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT sim_id, last_update_ts, online FROM simulators")
    rows = cur.fetchall()

    for sim_id, last_ts, online in rows:
        if last_ts is None:
            continue

        if int(online) == 1 and (now - int(last_ts) > SENDER_TIMEOUT):
            cur.execute("UPDATE simulators SET online=0 WHERE sim_id=?", (sim_id,))

            # If it was in active motion, close it out
            cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
            am = cur.fetchone()
            if am:
                start = int(am[0])
                dur = max(0, now - start)
                cur.execute("""
                    INSERT INTO motion_sessions (sim_id, start_ts, end_ts, duration_sec)
                    VALUES (?, ?, ?, ?)
                """, (sim_id, start, now, dur))
                cur.execute("DELETE FROM active_motion WHERE sim_id=?", (sim_id,))

    conn.commit()
    conn.close()


# ============================================================
# Serial open
# ============================================================
def open_serial_port():
    if serial is None:
        raise RuntimeError("pyserial not installed")

    if PREFERRED_PORT:
        try:
            return serial.Serial(PREFERRED_PORT, BAUD, timeout=1)
        except Exception:
            pass

    for p in serial.tools.list_ports.comports():
        try:
            return serial.Serial(p.device, BAUD, timeout=1)
        except Exception:
            continue

    raise RuntimeError("No serial ports available")


# ============================================================
# Main loop
# ============================================================
def run_service():
    init_db()

    try:
        ser = open_serial_port()
        print(f"[SimMonitorService] Opened serial port {ser.port}")
    except Exception as e:
        print(f"[SimMonitorService] Failed to open serial port: {e}")
        update_receiver_status(False)
        return

    receiver_last_seen = 0.0
    update_receiver_status(False)

    last_timeout_check = 0.0

    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            now = time.time()

            if line:
                mR = R_RE.match(line)
                mO = O_RE.match(line)
                mS = S_RE.match(line)

                if mR or mO or mS:
                    receiver_last_seen = now
                    update_receiver_status(True)

                if mR:
                    pass

                elif mO:
                    sim_id = int(mO.group(1))
                    online = int(mO.group(2))
                    set_sender_online(sim_id, bool(online))

                elif mS:
                    sim_id = int(mS.group(1))
                    motion = int(mS.group(2))
                    ramp = int(mS.group(3))
                    # seq = int(mS.group(4))  # available if you want logging

                    update_sender_state(sim_id, motion, ramp)
                    handle_motion(sim_id, motion)

            # receiver silence timeout
            if receiver_last_seen and (now - receiver_last_seen > RECEIVER_TIMEOUT):
                update_receiver_status(False)
                receiver_last_seen = 0.0

            # periodic sender timeout checks
            if now - last_timeout_check > 5:
                check_sender_timeouts()
                last_timeout_check = now

    except KeyboardInterrupt:
        print("[SimMonitorService] Stopped by user")
    except Exception as e:
        print(f"[SimMonitorService] Error in loop: {e}")
    finally:
        try:
            ser.close()
        except Exception:
            pass
        update_receiver_status(False)


if __name__ == "__main__":
    run_service()