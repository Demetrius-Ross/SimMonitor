# serial_handler_qt.py
"""
Qt-friendly Serial Monitor for the Sim-Monitor GUI
-------------------------------------------------
• Works on Windows (“COMx”) and Linux (“/dev/ttyUSBx”)
• Uses the exact LINE-PARSING logic from your working version
• NOW includes: Offline timeout detection per simulator
• Dispatches GUI-updates safely back to the Qt thread
"""

import logging, threading, time, re, sys
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

try:
    import serial, serial.tools.list_ports
except ImportError:
    serial = None

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DEBUG_MODE   = False
SERIAL_PORT  = "COM3"
BAUD_RATE    = 115200
READ_TIMEOUT = 1.0

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%message)s")

# ----------------------------------------------------------------------
# Regex
# ----------------------------------------------------------------------
data_regex = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$'
)
heartbeat_regex = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$'
)

# ----------------------------------------------------------------------
# Public toggles
# ----------------------------------------------------------------------
def set_debug_mode(enabled: bool):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    logger.info(f"Serial debug mode set to: {'DEBUG' if enabled else 'LIVE'}")

def stop_serial_thread():
    global _RUN_FLAG
    _RUN_FLAG = False

# ----------------------------------------------------------------------
# Main entry — start_serial_thread(...)
# ----------------------------------------------------------------------
def start_serial_thread(sim_cards: dict, *, update_sim_fn, mark_offline_fn):
    """
    sim_cards       -> { id: SimulatorCard }
    update_sim_fn   -> update_simulator_state(id, motion, ramp)
    mark_offline_fn -> set_simulator_offline(id, bool)
    """
    global _RUN_FLAG
    _RUN_FLAG = True

    # ---------------- MOCK SERIAL FOR DEBUG MODE ----------------
    class MockSerial:
        lines = [
            b"[HEARTBEAT] Received from Sender ID 2: RampState=0, MotionState=2, Seq=4979\n",
            b"[DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54\n",
            b"[DATA] Received from Sender ID 4: RampState=0, MotionState=1, Seq=54\n",
        ]
        def __init__(self):
            self.idx = 0

        def readline(self):
            time.sleep(2)
            l = self.lines[self.idx % len(self.lines)]
            self.idx += 1
            return l

        @property
        def is_open(self): return True
        def close(self): pass

    # ---------------- OPEN SERIAL PORT ----------------
    def open_any_serial_port(preferred: str, baud: int):
        if DEBUG_MODE or serial is None:
            logger.info("Using MockSerial (DEBUG mode)")
            return MockSerial()

        try:
            if preferred:
                s = serial.Serial(preferred, baud, timeout=READ_TIMEOUT)
                logger.info(f"Opened preferred port {preferred}")
                return s
        except Exception as exc:
            logger.warning(f"Preferred port failed: {exc}")

        logger.info("Scanning serial ports …")
        for p in serial.tools.list_ports.comports():
            try:
                s = serial.Serial(p.device, baud, timeout=READ_TIMEOUT)
                logger.info(f"Opened {p.device}")
                return s
            except Exception:
                continue

        raise IOError("No serial ports available")

    # ---------------- WORKER THREAD ----------------
    def reader_thread():
        ser = None
        try:
            ser = open_any_serial_port(SERIAL_PORT, BAUD_RATE)

            # Last-seen timestamps
            last_seen = {}
            OFFLINE_TIMEOUT = 10  # seconds

            while _RUN_FLAG:
                raw = ser.readline().decode(errors="replace").strip()
                now = time.time()

                if raw:
                    logger.debug(f"RX: {raw}")

                    m = data_regex.match(raw) or heartbeat_regex.match(raw)
                    if m:
                        sid = int(m.group(1))
                        ramp = int(m.group(2))
                        mot = int(m.group(3))

                        # Mark last seen time
                        last_seen[sid] = now

                        # Mark online
                        QMetaObject.invokeMethod(
                            mark_offline_fn.__self__,
                            "set_simulator_offline",
                            Qt.QueuedConnection,
                            Q_ARG(int, sid),
                            Q_ARG(bool, False)
                        )

                        # Update state
                        QMetaObject.invokeMethod(
                            update_sim_fn.__self__,
                            "update_simulator_state",
                            Qt.QueuedConnection,
                            Q_ARG(int, sid),
                            Q_ARG(int, mot),
                            Q_ARG(int, ramp)
                        )

                # ---------------- OFFLINE TIMEOUT CHECK ----------------
                for sim_id in sim_cards.keys():
                    last = last_seen.get(sim_id, 0)
                    if now - last > OFFLINE_TIMEOUT:
                        QMetaObject.invokeMethod(
                            mark_offline_fn.__self__,
                            "set_simulator_offline",
                            Qt.QueuedConnection,
                            Q_ARG(int, sim_id),
                            Q_ARG(bool, True)
                        )

        except Exception as exc:
            logger.error(f"Serial worker error: {exc}")

        finally:
            if ser and ser.is_open:
                ser.close()
                logger.info("Serial port closed.")

    # Start thread
    threading.Thread(target=reader_thread, daemon=True).start()