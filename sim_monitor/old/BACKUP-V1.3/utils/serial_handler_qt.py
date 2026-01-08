# serial_handler_qt.py
"""
Qt-friendly Serial Monitor for the Sim-Monitor GUI
--------------------------------------------------
• Real serial reading in LIVE mode
• Mock serial input in DEBUG mode (auto-simulated disconnects)
• Fake DATA / HEARTBEAT injection (for Debug Control Panel)
• Accurate receiver ESP32 online/offline detection
• Per-sender offline detection (heartbeat timeout)
• Thread-safe Qt signal dispatching
"""

import logging, threading, time, re
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

try:
    import serial, serial.tools.list_ports
except ImportError:
    serial = None


# ===============================================================
#   DEBUG INJECTION ENGINE
# ===============================================================
class DebugInjection:
    """
    Allows:
    • Fake DATA injection
    • Fake HEARTBEAT injection
    • Forcing sender disconnect
    """

    def __init__(self):
        self.disconnect_flags = {}   # sid → True/False
        self._inject_buffer = []     # queued raw bytes

    def toggle_disconnect(self, sid, enabled):
        self.disconnect_flags[sid] = enabled

    def inject_fake_data(self, sid):
        line = (
            f"[DATA] Received from Sender ID {sid}: "
            f"RampState=2, MotionState=1, Seq=9999\n"
        )
        self._inject_buffer.append(line.encode())

    def inject_fake_heartbeat(self, sid):
        line = (
            f"[HEARTBEAT] Received from Sender ID {sid}: "
            f"RampState=1, MotionState=2, Seq=10000\n"
        )
        self._inject_buffer.append(line.encode())

    def reset_to_normal(self):
        self.disconnect_flags.clear()


# Global debug object
serial_debug = DebugInjection()


# ===============================================================
#   CONFIG
# ===============================================================
DEBUG_MODE = False
SERIAL_PORT = ""
BAUD_RATE = 115200
READ_TIMEOUT = 1.0

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

data_regex = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),'
    r'\s+MotionState=(\d+),\s+Seq=(\d+)$'
)

heartbeat_regex = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),'
    r'\s+MotionState=(\d+),\s+Seq=(\d+)$'
)


# ===============================================================
#   FUNCTIONS CALLED BY main_qt
# ===============================================================
def set_debug_mode(enabled: bool):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    logger.info(f"Debug mode: {'ON' if enabled else 'OFF'}")


def stop_serial_thread():
    global _RUN_FLAG
    _RUN_FLAG = False


# ===============================================================
#   MAIN ENTRY POINT
# ===============================================================
def start_serial_thread(sim_cards: dict, *, update_sim_fn, mark_offline_fn, receiver_status_fn):
    """
    sim_cards: dict of {sim_id : SimulatorCard}
    update_sim_fn: MainWindow.update_simulator_state
    mark_offline_fn: MainWindow.set_simulator_offline
    receiver_status_fn: MainWindow.set_receiver_status
    """
    global _RUN_FLAG
    _RUN_FLAG = True

    # ===========================================================
    #   DEBUG MODE: simulated serial input
    # ===========================================================
    class MockSerial:
        """
        Simulated ESP32 receiver behavior:
        • Sends sample frames for 10 seconds
        • Then completely silent for 12 seconds
        • Repeats forever
        • Works with Debug Control Panel injection
        """

        def __init__(self):
            self.phase = "sending"
            self.last_phase_change = time.time()
            self.idx = 0

            self.frames = [
                b"[DATA] Received from Sender ID 1: RampState=2, MotionState=2, Seq=10\n",
                b"[HEARTBEAT] Received from Sender ID 2: RampState=1, MotionState=1, Seq=11\n",
            ]

        @property
        def is_open(self):
            return True

        def close(self):
            pass

        def readline(self):

            # FIRST: process injected frames
            if serial_debug._inject_buffer:
                return serial_debug._inject_buffer.pop(0)

            now = time.time()

            # Active sending
            if self.phase == "sending":
                if now - self.last_phase_change < 10:
                    time.sleep(1)
                    out = self.frames[self.idx % len(self.frames)]
                    self.idx += 1
                    return out
                else:
                    self.phase = "silent"
                    self.last_phase_change = now
                    return b""

            # Silent window
            if self.phase == "silent":
                if now - self.last_phase_change < 12:
                    time.sleep(1)
                    return b""
                else:
                    self.phase = "sending"
                    self.last_phase_change = now
                    return b""

            return b""

    # ===========================================================
    #   SERIAL PORT OPEN
    # ===========================================================
    def open_port(preferred):
        if DEBUG_MODE or serial is None:
            logger.info("DEBUG MODE: Using MockSerial")
            return MockSerial()

        # Try preferred port first
        try:
            if preferred:
                s = serial.Serial(preferred, BAUD_RATE, timeout=READ_TIMEOUT)
                logger.info(f"Opened {preferred}")
                return s
        except Exception as e:
            logger.warning(f"Cannot open preferred port {preferred}: {e}")

        # Auto-scan all ports
        logger.info("Scanning serial ports…")
        for port in serial.tools.list_ports.comports():
            try:
                s = serial.Serial(port.device, BAUD_RATE, timeout=READ_TIMEOUT)
                logger.info(f"Opened {port.device}")
                return s
            except:
                continue

        raise IOError("No serial ports found")

    # ===========================================================
    #   SERIAL THREAD
    # ===========================================================
    def reader_thread():
        ser = None
        try:
            # Attempt to open port
            ser = open_port(SERIAL_PORT)

            # Receiver ONLINE when port opens
            QMetaObject.invokeMethod(
                receiver_status_fn.__self__,
                "set_receiver_status",
                Qt.QueuedConnection,
                Q_ARG(bool, True)
            )

            # Sender last-seen timestamps
            last_seen = {}
            SENDER_TIMEOUT = 180

            while _RUN_FLAG:

                # Read one line
                raw = ser.readline().decode(errors="replace").strip()

                # If port is open, receiver is online.
                QMetaObject.invokeMethod(
                    receiver_status_fn.__self__,
                    "set_receiver_status",
                    Qt.QueuedConnection,
                    Q_ARG(bool, True)
                )

                if not raw:
                    continue  # silent waiting, still online

                m = data_regex.match(raw) or heartbeat_regex.match(raw)
                if not m:
                    continue

                sid = int(m.group(1))
                ramp = int(m.group(2))
                mot = int(m.group(3))

                # Forced disconnect via Debug Panel
                if serial_debug.disconnect_flags.get(sid, False):
                    continue

                # Update last-seen timestamp
                last_seen[sid] = time.time()

                # Mark sender ONLINE
                QMetaObject.invokeMethod(
                    mark_offline_fn.__self__,
                    "set_simulator_offline",
                    Qt.QueuedConnection,
                    Q_ARG(int, sid),
                    Q_ARG(bool, False)
                )

                # Update sender state
                QMetaObject.invokeMethod(
                    update_sim_fn.__self__,
                    "update_simulator_state",
                    Qt.QueuedConnection,
                    Q_ARG(int, sid),
                    Q_ARG(int, mot),
                    Q_ARG(int, ramp)
                )

                # Check sender timeouts
                now = time.time()
                for sim_id in sim_cards:
                    last = last_seen.get(sim_id, 0)
                    if now - last > SENDER_TIMEOUT:
                        QMetaObject.invokeMethod(
                            mark_offline_fn.__self__,
                            "set_simulator_offline",
                            Qt.QueuedConnection,
                            Q_ARG(int, sim_id),
                            Q_ARG(bool, True)
                        )

        except Exception as exc:
            logger.error(f"Serial worker error: {exc}")

            # Receiver OFFLINE on serial failure
            QMetaObject.invokeMethod(
                receiver_status_fn.__self__,
                "set_receiver_status",
                Qt.QueuedConnection,
                Q_ARG(bool, False)
            )

        finally:
            if ser and hasattr(ser, "is_open") and ser.is_open:
                ser.close()
                logger.info("Serial port closed.")

            # Final offline state
            QMetaObject.invokeMethod(
                receiver_status_fn.__self__,
                "set_receiver_status",
                Qt.QueuedConnection,
                Q_ARG(bool, False)
            )

    # ===========================================================
    #   START THREAD
    # ===========================================================
    threading.Thread(target=reader_thread, daemon=True).start()