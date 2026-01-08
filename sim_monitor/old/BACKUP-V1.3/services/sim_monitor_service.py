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

# Match your ESP32 serial prints
DATA_RE = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),'
)
HB_RE = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+)'
)

SENDER_TIMEOUT = 100      # seconds before marking sender offline
BAUD = 115200
PREFERRED_PORT = "/dev/ttyUSB0"      # e.g. "/dev/ttyUSB0" or "COM3" if you know it


def update_receiver_status(online: bool):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE system_status SET receiver_online=?, last_seen=? WHERE id=1",
        (1 if online else 0, int(time.time()))
    )
    conn.commit()
    conn.close()


def update_sender(sim_id, motion, ramp):
    now = int(time.time())
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


def handle_motion(sim_id, motion_state):
    conn = get_conn()
    cur = conn.cursor()

    # Check if sim is currently in an active motion session
    cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
    row = cur.fetchone()
    in_motion = row is not None
    now = int(time.time())

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


def open_serial_port():
    if serial is None:
        raise RuntimeError("pyserial not installed")

    # Try preferred port if you have it
    if PREFERRED_PORT:
        try:
            return serial.Serial(PREFERRED_PORT, BAUD, timeout=1)
        except Exception:
            pass

    # Otherwise auto-scan ports
    for p in serial.tools.list_ports.comports():
        try:
            return serial.Serial(p.device, BAUD, timeout=1)
        except Exception:
            continue

    raise RuntimeError("No serial ports available")


def run_service():
    init_db()
    try:
        ser = open_serial_port()
        print(f"[SimMonitorService] Opened serial port {ser.port}")
        update_receiver_status(True)
    except Exception as e:
        print(f"[SimMonitorService] Failed to open serial port: {e}")
        update_receiver_status(False)
        return

    last_timeout_check = 0
    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                m = DATA_RE.match(line) or HB_RE.match(line)
                if m:
                    sim_id = int(m.group(1))
                    ramp = int(m.group(2))
                    motion = int(m.group(3))
                    update_sender(sim_id, motion, ramp)
                    handle_motion(sim_id, motion)
                    update_receiver_status(True)

            now = time.time()
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
