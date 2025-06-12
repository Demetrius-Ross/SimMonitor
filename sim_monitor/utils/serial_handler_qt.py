# utils/serial_handler_qt.py  (Unified version 2025-05-29)

import time, threading, logging, re
from PyQt5.QtCore import QTimer

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None        # PySerial may be missing in dev environment

DEBUG_MODE  = True
SERIAL_PORT = "/dev/ttyUSB0"   # preferred port
BAUD_RATE   = 115200
chosen_port = None             # last good port (auto-scan)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# ── Regex patterns ─────────────────────────────────────────────────────────
data_regex = re.compile(
    r'\[DATA\]\s+Received from Sender ID\s+(\d+):\s+'
    r'RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)'
)
heartbeat_regex = re.compile(
    r'\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+'
    r'RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)'
)

# ── Globals for thread coordination ────────────────────────────────────────
active_senders     = {}            # {id: {last_seen, retry, offline}}
serial_thread_flag = threading.Event()   # set() when thread should run

# ───────────────────────────────────────────────────────────────────────────
# Public helpers
# ───────────────────────────────────────────────────────────────────────────
def set_debug_mode(enabled: bool):
    """Switch Debug/LIVE and restart thread if needed."""
    global DEBUG_MODE
    DEBUG_MODE = enabled
    stop_serial_thread()
    logger.info("Serial debug mode set to: %s", 'DEBUG' if enabled else 'LIVE')

def stop_serial_thread():
    """Signal thread to stop."""
    serial_thread_flag.clear()

def start_serial_thread(simulator_map, update_sim_fn, mark_offline_fn):
    """
    Kick off serial reader + offline heartbeat checker.
    Each callback runs in GUI thread via QTimer.singleShot(0,…).
    """
    if serial_thread_flag.is_set():
        return          # already running
    serial_thread_flag.set()

    # ── MockSerial (unchanged) ────────────────────────────────────────────
    class MockSerial:
        def __init__(self):
            self.lines = [
                b"[DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54\n",
                b"[HEARTBEAT] Received from Sender ID 2: RampState=2, MotionState=2, Seq=88\n",
                b"[DATA] Received from Sender ID 3: RampState=1, MotionState=0, Seq=99\n",
                b"[DATA] Received from Sender ID 4: RampState=2, MotionState=1, Seq=54\n",
            ]
            self.idx = 0
        def readline(self):
            if self.idx < len(self.lines):
                line = self.lines[self.idx]; self.idx += 1
                return line
            time.sleep(0.5)
            return b''
        @property
        def is_open(self): return True
        def close(self): pass

    # ── Port-scanning helper (from original file) ─────────────────────────
    def open_any_serial_port(preferred, baud):
        global chosen_port
        if DEBUG_MODE or serial is None:
            logger.info("Using MockSerial (Debug mode)")
            return MockSerial()

        # 1. Try preferred
        try:
            ser = serial.Serial(preferred, baud, timeout=1)
            chosen_port = ser.port
            logger.info("Opened preferred port %s", preferred)
            return ser
        except Exception as e:
            logger.warning("Preferred port %s failed: %s", preferred, e)

        # 2. Scan all ports
        for p in serial.tools.list_ports.comports():
            try:
                ser = serial.Serial(p.device, baud, timeout=1)
                chosen_port = ser.port
                logger.info("Opened fallback port %s", p.device)
                return ser
            except Exception:
                continue

        raise IOError("No serial ports found")

    # ── Helper to mark activity & offline status ──────────────────────────
    def _mark_active(sid):
        now = time.time()
        info = active_senders.setdefault(sid, {'last_seen':0,'retry':0,'offline':True})
        info['last_seen'] = now
        info['retry']     = 0
        if info['offline']:
            info['offline'] = False
            QTimer.singleShot(0, lambda: mark_offline_fn(sid, False))

    def offline_check():
        now = time.time()
        for sid, info in list(active_senders.items()):
            if info['offline']:
                continue
            if now - info['last_seen'] > 30:
                info['retry'] += 1
                if info['retry'] >= 3:
                    info['offline'] = True
                    logger.warning("Sender %s OFFLINE", sid)
                    QTimer.singleShot(0, lambda sid=sid: mark_offline_fn(sid, True))
        if serial_thread_flag.is_set():
            QTimer.singleShot(5000, offline_check)

    # ── Serial worker thread ──────────────────────────────────────────────
    def serial_worker():
        try:
            ser = open_any_serial_port(SERIAL_PORT, BAUD_RATE)
        except Exception as e:
            logger.error("Serial init failed: %s", e)
            return

        while serial_thread_flag.is_set():
            try:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode(errors='replace').strip()
                logger.debug("LINE %s", line)

                m = data_regex.match(line) or heartbeat_regex.match(line)
                if not m:
                    continue

                sid   = int(m.group(1))
                ramp  = int(m.group(2))
                motion= int(m.group(3))
                _mark_active(sid)

                if sid in simulator_map:
                    QTimer.singleShot(0,
                        lambda sid=sid, r=ramp, m=motion:
                            update_sim_fn(sid, m, r))
            except Exception as e:
                logger.error("Serial thread error: %s", e)
                time.sleep(1)

        # Thread stopping → close port
        try:
            ser.close()
        except Exception:
            pass
        logger.info("Serial thread exited")

    # ── start everything ─────────────────────────────────────────────────
    QTimer.singleShot(5000, offline_check)
    threading.Thread(target=serial_worker, daemon=True).start()
