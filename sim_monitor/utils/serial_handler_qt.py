# serial_handler_qt.py

import time
import threading
import logging
import re
from PyQt5.QtCore import QTimer

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

DEBUG_MODE = True
SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

# Regex patterns
data_regex = re.compile(
    r'\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)'
)
heartbeat_regex = re.compile(
    r'\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)'
)

active_senders = {}
serial_thread_flag = threading.Event()

def set_debug_mode(enabled: bool):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    serial_thread_flag.clear()  # stop any existing thread
    logger.info(f"Serial debug mode set to: {'DEBUG' if enabled else 'LIVE'}")

def stop_serial_thread():
    """Signal the serial thread to stop."""
    serial_thread_flag.clear()

def start_serial_thread(simulator_map, update_sim_fn, mark_offline_fn):
    """Starts the serial reader and offline checker in threads."""
    if serial_thread_flag.is_set():
        return  # already running
    serial_thread_flag.set()

    class MockSerial:
        def __init__(self):
            self.lines = [
                b"[DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54\n",
                b"[HEARTBEAT] Received from Sender ID 2: RampState=2, MotionState=2, Seq=88\n",
                b"[DATA] Received from Sender ID 3: RampState=1, MotionState=0, Seq=99\n",
                b"[DATA] Received from Sender ID 4: RampState=2, MotionState=1, Seq=54\n",
            ]
            self.index = 0

        def readline(self):
            if self.index < len(self.lines):
                line = self.lines[self.index]
                self.index += 1
                return line
            time.sleep(0.5)  # slight delay when idle
            return b''

        @property
        def is_open(self):
            return True

        def close(self):
            pass

    def open_serial():
        if DEBUG_MODE or serial is None:
            logger.info("Using Mock Serial (debug mode)")
            return MockSerial()
        try:
            return serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        except Exception as e:
            logger.warning(f"Failed to open serial port: {e}")
            return None

    def _mark_active(sender_id):
        now = time.time()
        if sender_id not in active_senders:
            active_senders[sender_id] = {'last_seen': now, 'retry': 0, 'offline': False}
        else:
            info = active_senders[sender_id]
            info['last_seen'] = now
            info['retry'] = 0
            if info['offline']:
                info['offline'] = False
                QTimer.singleShot(0, lambda: mark_offline_fn(sender_id, False))

    def offline_check():
        now = time.time()
        for sid, info in active_senders.items():
            if not info['offline'] and now - info['last_seen'] > 30:
                info['retry'] += 1
                logger.warning(f"Sender {sid} missed heartbeat ({info['retry']})")
                if info['retry'] >= 3:
                    info['offline'] = True
                    QTimer.singleShot(0, lambda sid=sid: mark_offline_fn(sid, True))
        if serial_thread_flag.is_set():
            QTimer.singleShot(5000, offline_check)

    def serial_worker():
        ser = open_serial()
        if not ser:
            logger.error("No serial port available.")
            return

        while serial_thread_flag.is_set():
            try:
                line = ser.readline().decode().strip()
                if not line:
                    continue
                logger.debug(f"Serial Line: {line}")

                match = data_regex.match(line) or heartbeat_regex.match(line)
                if match:
                    sid = int(match.group(1))
                    ramp = int(match.group(2))
                    motion = int(match.group(3))
                    _mark_active(sid)

                    if sid in simulator_map:
                        QTimer.singleShot(0, lambda sid=sid, m=motion, r=ramp:
                            update_sim_fn(sid, m, r)
                        )
                else:
                    logger.warning(f"Ignored line: {line}")
            except Exception as e:
                logger.error(f"Error in serial thread: {e}")
                time.sleep(1)

    QTimer.singleShot(5000, offline_check)
    threading.Thread(target=serial_worker, daemon=True).start()
