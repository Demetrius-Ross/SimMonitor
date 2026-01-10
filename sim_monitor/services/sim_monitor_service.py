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
# NEW CSV protocol from receiver
# -----------------------------
RECV_RE = re.compile(r"^R,1$")
ONLINE_RE = re.compile(r"^O,(\d+),(0|1)$")
STATE_RE = re.compile(r"^S,(\d+),(\d+),(\d+),(\d+)$")  # sid,motion,ramp,seq

BAUD = 115200
PREFERRED_PORT = "/dev/ttyUSB0"   # change if needed
SERIAL_TIMEOUT = 1.0

# If we see no valid frames for this many seconds, receiver is considered offline
RECEIVER_TIMEOUT = 20

# Sender offline based on DB last_update_ts
SENDER_TIMEOUT = 180


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

    # Motion starts (In Operation)
    if motion_state == 2 and not in_motion:
        cur.execute(
            "INSERT OR REPLACE INTO active_motion (sim_id, start_ts) VALUES (?, ?)",
            (sim_id, now)
        )

    # Motion ends (anything other than 2)
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


def open_serial_port():
    if serial is None:
        raise RuntimeError("pyserial not installed")

    # Try preferred port first
    if PREFERRED_PORT:
        try:
            s = serial.Serial(PREFERRED_PORT, BAUD, timeout=SERIAL_TIMEOUT)
            return s
        except Exception:
            pass

    # Auto-scan ports
    for p in serial.tools.list_ports.comports():
        try:
            s = serial.Serial(p.device, BAUD, timeout=SERIAL_TIMEOUT)
            return s
        except Exception:
            continue

    raise RuntimeError("No serial ports available")


def run_service():
    init_db()

    last_valid_frame_ts = 0
    receiver_marked_online = False
    last_timeout_check = 0

    try:
        ser = open_serial_port()
        print(f"[SimMonitorService] Opened serial port {ser.port}")

        # Clear junk at boot so first valid frame isn't delayed behind noise
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        # Don't mark online just for opening port — wait for a valid frame
        update_receiver_status(False)
    except Exception as e:
        print(f"[SimMonitorService] Failed to open serial port: {e}")
        update_receiver_status(False)
        return

    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            now = int(time.time())

            # Periodic sender timeout cleanup
            if now - last_timeout_check > 5:
                check_sender_timeouts()
                last_timeout_check = now

            if not line:
                # Receiver offline if no valid frame within RECEIVER_TIMEOUT
                if receiver_marked_online and last_valid_frame_ts and (now - last_valid_frame_ts > RECEIVER_TIMEOUT):
                    receiver_marked_online = False
                    update_receiver_status(False, ts=now)
                continue

            # Parse valid frames
            mR = RECV_RE.match(line)
            mO = ONLINE_RE.match(line)
            mS = STATE_RE.match(line)

            if not (mR or mO or mS):
                # Ignore non-protocol noise
                continue

            # Any valid frame => receiver alive
            last_valid_frame_ts = now
            if not receiver_marked_online:
                receiver_marked_online = True
            update_receiver_status(True, ts=now)

            # R,1 (keepalive) - nothing else to do
            if mR:
                continue

            # O,sid,0|1
            if mO:
                sid = int(mO.group(1))
                online = int(mO.group(2))
                set_sender_online_flag(sid, bool(online), ts=now)
                continue

            # S,sid,motion,ramp,seq
            if mS:
                sid = int(mS.group(1))
                motion = int(mS.group(2))
                ramp = int(mS.group(3))
                # seq = int(mS.group(4))

                update_sender(sid, motion, ramp, ts=now)
                handle_motion(sid, motion, ts=now)

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