# utils/serial_handler_qt.py
"""
DB-backed Serial Monitor for the Sim-Monitor GUI (Option A)
-----------------------------------------------------------
Your GUI updates ONLY from SQLite via MainWindow.refresh_from_db().
Therefore this module must write parsed serial frames into the DB.

Frames from ESP32 receiver (CSV):
  R,1
  O,<sid>,<0|1>
  S,<sid>,<motion>,<ramp>,<seq>

Receiver Online Logic:
• Receiver is ONLINE if ANY valid frame is received (R/O/S)
• Receiver OFFLINE if no valid frame for RECEIVER_TIMEOUT seconds

Sender Online Logic:
• Sender ONLINE on O=1 or any S frame
• Sender OFFLINE on O=0 or inactivity > SENDER_TIMEOUT seconds
"""

import logging, threading, time, re

try:
    import serial, serial.tools.list_ports
except ImportError:
    serial = None

from utils.db import get_conn  # MUST match the same DB your GUI reads


# ===============================================================
#   DEBUG INJECTION ENGINE
# ===============================================================
class DebugInjection:
    def __init__(self):
        self.disconnect_flags = {}   # sid -> True/False
        self._inject_buffer = []     # queued raw bytes

    def toggle_disconnect(self, sid, enabled):
        self.disconnect_flags[sid] = enabled

    def inject_receiver_alive(self):
        self._inject_buffer.append(b"R,1\n")

    def inject_sender_online(self, sid):
        self._inject_buffer.append(f"O,{sid},1\n".encode())

    def inject_sender_offline(self, sid):
        self._inject_buffer.append(f"O,{sid},0\n".encode())

    def inject_state(self, sid, motion=2, ramp=1, seq=9999):
        self._inject_buffer.append(f"S,{sid},{motion},{ramp},{seq}\n".encode())

    def reset_to_normal(self):
        self.disconnect_flags.clear()
        self._inject_buffer.clear()


serial_debug = DebugInjection()


# ===============================================================
#   CONFIG
# ===============================================================
DEBUG_MODE = False
SERIAL_PORT = ""     # set to "COMx" to force; else auto-scan
BAUD_RATE = 115200
READ_TIMEOUT = 1.0

RECEIVER_TIMEOUT = 20.0
SENDER_TIMEOUT = 180.0

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ===============================================================
#   CSV FRAME REGEX
# ===============================================================
receiver_regex = re.compile(r"^R,1$")
online_regex   = re.compile(r"^O,(\d+),(0|1)$")
state_regex    = re.compile(r"^S,(\d+),(\d+),(\d+),(\d+)$")


# ===============================================================
#   PUBLIC API used by main_qt
# ===============================================================
def set_debug_mode(enabled: bool):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    logger.info(f"Debug mode: {'ON' if enabled else 'OFF'}")


def stop_serial_thread():
    global _RUN_FLAG
    _RUN_FLAG = False


# ===============================================================
#   DB helpers (match refresh_from_db tables)
# ===============================================================
def _db_set_receiver_online(conn, online: bool):
    cur = conn.cursor()
    cur.execute("UPDATE system_status SET receiver_online=? WHERE id=1", (1 if online else 0,))
    conn.commit()

def _db_touch_sim(conn, sim_id: int):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO simulators (sim_id, motion_state, ramp_state, online, last_update_ts)
        VALUES (?, 0, 0, 0, ?)
    """, (sim_id, int(time.time())))
    conn.commit()

def _db_set_sim_online(conn, sim_id: int, online: bool):
    _db_touch_sim(conn, sim_id)
    cur = conn.cursor()
    cur.execute("""
        UPDATE simulators
        SET online=?, last_update_ts=?
        WHERE sim_id=?
    """, (1 if online else 0, int(time.time()), sim_id))
    conn.commit()

def _db_update_sim_state(conn, sim_id: int, motion: int, ramp: int):
    """
    Update simulators + manage active_motion / motion_sessions.
    Assumption from your receiver firmware:
      motion_state == 1  => in motion
      motion_state == 2  => home / not moving
    """
    now_ts = int(time.time())
    in_motion = (motion == 1)

    _db_touch_sim(conn, sim_id)
    cur = conn.cursor()

    # Update current state + mark online
    cur.execute("""
        UPDATE simulators
        SET motion_state=?, ramp_state=?, online=1, last_update_ts=?
        WHERE sim_id=?
    """, (motion, ramp, now_ts, sim_id))

    # Motion session tracking
    cur.execute("SELECT start_ts FROM active_motion WHERE sim_id=?", (sim_id,))
    active = cur.fetchone()

    if in_motion and not active:
        cur.execute("INSERT OR REPLACE INTO active_motion (sim_id, start_ts) VALUES (?, ?)", (sim_id, now_ts))

    if (not in_motion) and active:
        start_ts = int(active[0])
        end_ts = now_ts
        dur = max(0, end_ts - start_ts)

        cur.execute("DELETE FROM active_motion WHERE sim_id=?", (sim_id,))
        cur.execute("""
            INSERT INTO motion_sessions (sim_id, start_ts, end_ts, duration_sec)
            VALUES (?, ?, ?, ?)
        """, (sim_id, start_ts, end_ts, dur))

    conn.commit()


# ===============================================================
#   MAIN ENTRY POINT
# ===============================================================
def start_serial_thread(sim_cards: dict, *, update_sim_fn=None, mark_offline_fn=None, receiver_status_fn=None):
    """
    Kept compatible with your old call signature.
    We do NOT call Qt methods; we update DB only.
    """
    global _RUN_FLAG
    _RUN_FLAG = True

    # DEBUG serial
    class MockSerial:
        def __init__(self):
            self.idx = 0
            self.frames = [
                b"R,1\n",
                b"O,1,1\n",
                b"S,1,2,1,10\n",
                b"O,2,1\n",
                b"S,2,1,2,11\n",
            ]

        @property
        def is_open(self):
            return True

        def close(self):
            pass

        def readline(self):
            if serial_debug._inject_buffer:
                return serial_debug._inject_buffer.pop(0)
            time.sleep(0.6)
            out = self.frames[self.idx % len(self.frames)]
            self.idx += 1
            return out

    def open_port(preferred):
        if DEBUG_MODE or serial is None:
            logger.info("DEBUG MODE: Using MockSerial")
            return MockSerial()

        if preferred:
            try:
                s = serial.Serial(preferred, BAUD_RATE, timeout=READ_TIMEOUT)
                logger.info(f"Opened {preferred}")
                return s
            except Exception as e:
                logger.warning(f"Cannot open preferred port {preferred}: {e}")

        logger.info("Scanning serial ports…")
        for port in serial.tools.list_ports.comports():
            try:
                s = serial.Serial(port.device, BAUD_RATE, timeout=READ_TIMEOUT)
                logger.info(f"Opened {port.device}")
                return s
            except Exception:
                continue

        raise IOError("No serial ports found")

    def reader_thread():
        ser = None
        conn = None

        last_seen_sender = {}   # sid -> time.time()
        last_seen_receiver = 0.0
        receiver_online = False

        def set_receiver(flag: bool):
            nonlocal receiver_online
            if receiver_online == flag:
                return
            receiver_online = flag
            try:
                _db_set_receiver_online(conn, flag)
            except Exception as e:
                logger.error(f"DB receiver_online update failed: {e}")

        try:
            ser = open_port(SERIAL_PORT)

            # IMPORTANT: open DB connection inside the thread
            conn = get_conn()

            # Start offline until we see valid frames
            try:
                _db_set_receiver_online(conn, False)
            except Exception:
                pass

            while _RUN_FLAG:
                raw = ser.readline().decode(errors="replace").strip()
                now = time.time()

                # Receiver timeout
                if receiver_online and last_seen_receiver and (now - last_seen_receiver > RECEIVER_TIMEOUT):
                    set_receiver(False)

                # Sender inactivity timeout
                for sid, last in list(last_seen_sender.items()):
                    if last and (now - last > SENDER_TIMEOUT):
                        try:
                            _db_set_sim_online(conn, int(sid), False)
                        except Exception as e:
                            logger.error(f"DB sender offline update failed sid={sid}: {e}")

                if not raw:
                    continue

                mR = receiver_regex.match(raw)
                mO = online_regex.match(raw)
                mS = state_regex.match(raw)

                if not (mR or mO or mS):
                    continue

                # Any valid frame => receiver online
                last_seen_receiver = now
                set_receiver(True)

                if mR:
                    continue

                if mO:
                    sid = int(mO.group(1))
                    online = int(mO.group(2))

                    if serial_debug.disconnect_flags.get(sid, False):
                        continue

                    last_seen_sender[sid] = now
                    _db_set_sim_online(conn, sid, bool(online))
                    continue

                if mS:
                    sid = int(mS.group(1))
                    motion = int(mS.group(2))
                    ramp = int(mS.group(3))
                    # seq = int(mS.group(4))

                    if serial_debug.disconnect_flags.get(sid, False):
                        continue

                    last_seen_sender[sid] = now
                    _db_update_sim_state(conn, sid, motion, ramp)
                    continue

        except Exception as exc:
            logger.error(f"Serial worker error: {exc}")
            if conn:
                try:
                    _db_set_receiver_online(conn, False)
                except Exception:
                    pass

        finally:
            if ser and hasattr(ser, "is_open") and ser.is_open:
                try:
                    ser.close()
                except Exception:
                    pass
                logger.info("Serial port closed.")

            if conn:
                try:
                    _db_set_receiver_online(conn, False)
                    conn.close()
                except Exception:
                    pass

    threading.Thread(target=reader_thread, daemon=True).start()