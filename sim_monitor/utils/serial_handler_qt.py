# serial_handler_qt.py
"""
Qt-friendly Serial Monitor for the Sim-Monitor GUI
--------------------------------------------------
LIVE mode:
• Reads CSV frames from ESP32 receiver over USB serial

DEBUG mode:
• Mock serial input
• Debug injection: fake sender frames + forced sender disconnect

Receiver Online Logic (IMPROVED):
• Receiver is considered ONLINE if:
  - Any valid frame is received (R/O/S), OR
  - (optional) port-open counts as online
• Receiver is OFFLINE if no valid frame received for RECEIVER_TIMEOUT seconds

Sender Online Logic:
• Sender ONLINE on valid O/S frames
• Sender OFFLINE if no valid activity for SENDER_TIMEOUT seconds
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
    • Fake sender frames injection
    • Forcing sender disconnect
    """

    def __init__(self):
        self.disconnect_flags = {}   # sid → True/False
        self._inject_buffer = []     # queued raw bytes

    def toggle_disconnect(self, sid, enabled):
        self.disconnect_flags[sid] = enabled

    def inject_sender_online(self, sid):
        self._inject_buffer.append(f"O,{sid},1\n".encode())

    def inject_sender_offline(self, sid):
        self._inject_buffer.append(f"O,{sid},0\n".encode())

    def inject_state(self, sid, motion=2, ramp=1, seq=9999):
        self._inject_buffer.append(f"S,{sid},{motion},{ramp},{seq}\n".encode())

    def inject_receiver_alive(self):
        self._inject_buffer.append(b"R,1\n")

    def reset_to_normal(self):
        self.disconnect_flags.clear()
        self._inject_buffer.clear()


serial_debug = DebugInjection()


# ===============================================================
#   CONFIG
# ===============================================================
DEBUG_MODE = False
SERIAL_PORT = ""     # set to "COMx" to force, else auto-scan
BAUD_RATE = 115200
READ_TIMEOUT = 1.0

# Receiver considered offline if we don't see any valid frame in this time
RECEIVER_TIMEOUT = 20.0

# Sender considered offline if we don't see any activity for this time
SENDER_TIMEOUT = 180.0

# Optional: if True, "port opened successfully" marks receiver online even with no traffic
PORT_OPEN_COUNTS_AS_ONLINE = True


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ===============================================================
#   CSV FRAME REGEX
# ===============================================================
# R,1
receiver_regex = re.compile(r"^R,1$")

# O,<sid>,<0|1>
online_regex = re.compile(r"^O,(\d+),(0|1)$")

# S,<sid>,<motion>,<ramp>,<seq>
state_regex = re.compile(r"^S,(\d+),(\d+),(\d+),(\d+)$")


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
    update_sim_fn: MainWindow.update_simulator_state(sim_id, motion, ramp)
    mark_offline_fn: MainWindow.set_simulator_offline(sim_id, is_offline)
    receiver_status_fn: MainWindow.set_receiver_status(is_online)
    """

    global _RUN_FLAG
    _RUN_FLAG = True

    # ===========================================================
    #   DEBUG MODE SERIAL
    # ===========================================================
    class MockSerial:
        def __init__(self):
            self.last_emit = time.time()
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
            # injected frames first
            if serial_debug._inject_buffer:
                return serial_debug._inject_buffer.pop(0)

            time.sleep(0.6)
            out = self.frames[self.idx % len(self.frames)]
            self.idx += 1
            return out

    # ===========================================================
    #   SERIAL PORT OPEN
    # ===========================================================
    def open_port(preferred):
        if DEBUG_MODE or serial is None:
            logger.info("DEBUG MODE: Using MockSerial")
            return MockSerial()

        # Try preferred port first
        if preferred:
            try:
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
            except Exception:
                continue

        raise IOError("No serial ports found")

    # ===========================================================
    #   SERIAL THREAD
    # ===========================================================
    def reader_thread():
        ser = None

        # Sender last-seen timestamps
        last_seen_sender = {}

        # Receiver last-seen (any valid frame)
        last_seen_receiver = 0.0
        receiver_online = False

        def set_receiver_online(flag: bool):
            nonlocal receiver_online
            if receiver_online == flag:
                return
            receiver_online = flag
            QMetaObject.invokeMethod(
                receiver_status_fn.__self__,
                "set_receiver_status",
                Qt.QueuedConnection,
                Q_ARG(bool, flag)
            )

        def mark_sender_offline(sid: int, is_offline: bool):
            QMetaObject.invokeMethod(
                mark_offline_fn.__self__,
                "set_simulator_offline",
                Qt.QueuedConnection,
                Q_ARG(int, sid),
                Q_ARG(bool, is_offline)
            )

        def update_sender_state(sid: int, motion: int, ramp: int):
            QMetaObject.invokeMethod(
                update_sim_fn.__self__,
                "update_simulator_state",
                Qt.QueuedConnection,
                Q_ARG(int, sid),
                Q_ARG(int, motion),
                Q_ARG(int, ramp)
            )

        try:
            ser = open_port(SERIAL_PORT)

            # If you want port-open to count, set receiver online now
            if PORT_OPEN_COUNTS_AS_ONLINE:
                set_receiver_online(True)
                last_seen_receiver = time.time()

            while _RUN_FLAG:
                raw = ser.readline().decode(errors="replace").strip()

                now = time.time()

                # If silent, still enforce receiver timeout based on last valid frame
                if not raw:
                    if receiver_online and last_seen_receiver and (now - last_seen_receiver > RECEIVER_TIMEOUT):
                        set_receiver_online(False)

                    # sender timeout check even during silence
                    for sim_id in sim_cards:
                        last = last_seen_sender.get(sim_id, 0)
                        if last and (now - last > SENDER_TIMEOUT):
                            mark_sender_offline(sim_id, True)

                    continue

                # --- Parse frames ---
                # Any valid frame => receiver is online
                mR = receiver_regex.match(raw)
                mO = online_regex.match(raw)
                mS = state_regex.match(raw)

                if not (mR or mO or mS):
                    # not valid => ignore (don’t affect receiver online state)
                    continue

                # Any valid frame counts as receiver alive
                last_seen_receiver = now
                set_receiver_online(True)

                # Receiver heartbeat frame
                if mR:
                    continue

                # Sender online/offline frame
                if mO:
                    sid = int(mO.group(1))
                    online = int(mO.group(2))

                    if serial_debug.disconnect_flags.get(sid, False):
                        continue

                    if online == 1:
                        last_seen_sender[sid] = now
                        mark_sender_offline(sid, False)
                    else:
                        mark_sender_offline(sid, True)
                    continue

                # Sender state frame
                if mS:
                    sid = int(mS.group(1))
                    motion = int(mS.group(2))
                    ramp = int(mS.group(3))
                    # seq = int(mS.group(4))  # available if you want to display/log

                    if serial_debug.disconnect_flags.get(sid, False):
                        continue

                    last_seen_sender[sid] = now
                    mark_sender_offline(sid, False)
                    update_sender_state(sid, motion, ramp)

                    # After processing state, run sender timeouts
                    for sim_id in sim_cards:
                        last = last_seen_sender.get(sim_id, 0)
                        if last and (now - last > SENDER_TIMEOUT):
                            mark_sender_offline(sim_id, True)

        except Exception as exc:
            logger.error(f"Serial worker error: {exc}")
            set_receiver_online(False)

        finally:
            if ser and hasattr(ser, "is_open") and ser.is_open:
                ser.close()
                logger.info("Serial port closed.")

            set_receiver_online(False)

    threading.Thread(target=reader_thread, daemon=True).start()