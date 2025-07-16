# serial_handler_qt.py
"""
Qt-friendly Serial Monitor for the Sim-Monitor GUI
-------------------------------------------------
• Works on Windows (“COMx”) and Linux (“/dev/ttyUSBx”)
• Uses the exact LINE-PARSING logic that already proved reliable
  in your original serial_handler.py
• Dispatches GUI-updates safely back to the Qt thread
"""

import logging, threading, time, re, sys
from functools import partial
from PyQt5.QtCore import QTimer, QMetaObject, Qt, Q_ARG


try:
    import serial, serial.tools.list_ports        # real serial
except ImportError:
    serial = None                                 # PySerial not present

# ----------------------------------------------------------------------
#  Configuration  ------------------------------------------------------
# ----------------------------------------------------------------------
DEBUG_MODE   = False          # toggled by main_qt via set_debug_mode()
SERIAL_PORT  = "COM3"         # leave "" for “auto”, or hard-wire (e.g. COM3)
BAUD_RATE    = 115200
READ_TIMEOUT = 1.0            # seconds (blocks inside the worker-thread)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s:%(message)s")

# ----------------------------------------------------------------------
#  Regex (identical to your working code)
# ----------------------------------------------------------------------
data_regex = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$')
heartbeat_regex = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$')

# ----------------------------------------------------------------------
#  Public toggles called by your GUI
# ----------------------------------------------------------------------
def set_debug_mode(enabled: bool):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    logger.info(f"Serial debug mode set to: {'DEBUG' if enabled else 'LIVE'}")

def stop_serial_thread():
    """Set by your MainWindow.closeEvent()"""
    global _RUN_FLAG
    _RUN_FLAG = False


# ----------------------------------------------------------------------
#  Main entry:  start_serial_thread(...)
# ----------------------------------------------------------------------
def start_serial_thread(sim_cards: dict, *,
                        update_sim_fn, mark_offline_fn):
    """
    • sim_cards      -> { device_id: SimulatorCard }
    • update_sim_fn  -> callable(id, motion, ramp)
    • mark_offline_fn-> callable(id, offline_bool)

    Called once from main_qt.py after the UI is built.
    """
    global _RUN_FLAG
    _RUN_FLAG = True

    # -------------------------  helpers  ------------------------------
    class MockSerial:
        """When DEBUG_MODE=True – feed dummy frames every 2 s"""
        lines = [
            b"[HEARTBEAT] Received from Sender ID 2: RampState=0, MotionState=2, Seq=4979\n",
            b"[DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54\n",
            b"[DATA] Received from Sender ID 4: RampState=0, MotionState=1, Seq=54\n",
        ]
        def __init__(self):
            self.idx = 0
        def readline(self):                          # emulate blocking read
            time.sleep(2)
            l = self.lines[self.idx % len(self.lines)]
            self.idx += 1
            return l
        @property
        def is_open(self): return True
        def close(self): pass

    #  --- open port ---------------------------------------------------
    def open_any_serial_port(preferred: str, baud: int):
        if DEBUG_MODE or serial is None:
            logger.info("Using MockSerial   (DEBUG mode)")
            return MockSerial()

        # 1) try the preferred one first
        try:
            if preferred:
                s = serial.Serial(preferred, baud, timeout=READ_TIMEOUT)
                logger.info(f"Opened preferred port {preferred}")
                return s
        except Exception as exc:
            logger.warning(f"Preferred port failed: {exc}")

        # 2) scan everything the OS can see
        logger.info("Scanning serial ports …")
        for p in serial.tools.list_ports.comports():
            try:
                s = serial.Serial(p.device, baud, timeout=READ_TIMEOUT)
                logger.info(f"Opened {p.device}")
                return s
            except Exception:
                continue
        raise IOError("No serial ports available")

    #  --- worker thread ----------------------------------------------
    def reader_thread():
        ser = None
        try:
            ser = open_any_serial_port(SERIAL_PORT, BAUD_RATE)
            while _RUN_FLAG:
                raw = ser.readline().decode(errors="replace").strip()
                if not raw:
                    continue

                logger.debug(f"RX: {raw}")

                m = data_regex.match(raw) or heartbeat_regex.match(raw)
                if not m:
                    continue

                sid  = int(m.group(1))
                ramp = int(m.group(2))
                mot  = int(m.group(3))

                # dispatch *safely* back into Qt’s main thread
                QMetaObject.invokeMethod(
                    update_sim_fn.__self__,
                    "update_simulator_state",
                    Qt.QueuedConnection,
                    Q_ARG(int, sid),
                    Q_ARG(int, mot),
                    Q_ARG(int, ramp)
                )

        except Exception as exc:
            logger.error(f"Serial worker error: {exc}")
        finally:
            if ser and ser.is_open:
                ser.close()
                logger.info("Serial port closed.")

    #  --- launch! -----------------------------------------------------
    threading.Thread(target=reader_thread, daemon=True).start()
