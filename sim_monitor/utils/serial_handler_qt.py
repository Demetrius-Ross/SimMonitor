# serial_handler_qt.py
"""
Qt-friendly Serial Monitor for the Sim-Monitor GUI
--------------------------------------------------
• Real serial reading in LIVE mode
• Mock serial input in DEBUG mode (auto-simulated disconnects)
• Injection engine:
    - Fake STATE frames (CSV)
    - Fake ONLINE/OFFLINE frames (CSV)
    - Fake RECEIVER heartbeat frames (CSV)
    - Optional backward-compat injection of legacy verbose lines
• Accurate receiver ESP32 online/offline detection
    - Uses receiver heartbeat frames:  R,1
    - Falls back to "serial port open" (optional) + timeout
• Per-sender offline detection (timeout)
• Thread-safe Qt signal dispatching

NEW SERIAL PROTOCOL (recommended):
    R,1
    O,<sid>,<0|1>
    S,<sid>,<motion>,<ramp>,<seq>

Backward compatible with legacy verbose lines:
    [DATA] Received from Sender ID ...
    [HEARTBEAT] Received from Sender ID ...
"""

import logging
import threading
import time
import re
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
    • Fake STATE injection (CSV)
    • Fake ONLINE/OFFLINE injection (CSV)
    • Fake RECEIVER heartbeat injection (CSV)
    • Forcing sender disconnect (drops updates for that sender)
    """

    def __init__(self):
        self.disconnect_flags = {}   # sid -> True/False
        self._inject_buffer = []     # queued raw bytes

    def toggle_disconnect(self, sid, enabled: bool):
        self.disconnect_flags[sid] = enabled

    def inject_receiver_alive(self, alive: bool = True):
        # Receiver heartbeat frame
        line = f"R,{1 if alive else 0}\n"
        self._inject_buffer.append(line.encode())

    def inject_online(self, sid: int, online: bool = True):
        line = f"O,{sid},{1 if online else 0}\n"
        self._inject_buffer.append(line.encode())

    def inject_state(self, sid: int, motion: int = 2, ramp: int = 1, seq: int = 9999):
        line = f"S,{sid},{motion},{ramp},{seq}\n"
        self._inject_buffer.append(line.encode())

    # Optional legacy-format injectors (if you still want them)
    def inject_fake_data_legacy(self, sid: int):
        line = (
            f"[DATA] Received from Sender ID {sid}: "
            f"RampState=2, MotionState=1, Seq=9999\n"
        )
        self._inject_buffer.append(line.encode())

    def inject_fake_heartbeat_legacy(self, sid: int):
        line = (
            f"[HEARTBEAT] Received from Sender ID {sid}: "
            f"RampState=1, MotionState=2, Seq=10000\n"
        )
        self._inject_buffer.append(line.encode())

    def reset_to_normal(self):
        self.disconnect_flags.clear()
        self._inject_buffer.clear()


# Global debug object
serial_debug = DebugInjection()


# ===============================================================
#   CONFIG
# ===============================================================
DEBUG_MODE = False
SERIAL_PORT = ""      # optional preferred port; empty means auto-scan
BAUD_RATE = 115200
READ_TIMEOUT = 1.0

# Receiver heartbeat expectations (from ESP32 receiver):
RECEIVER_HEARTBEAT_TIMEOUT = 12.0   # seconds (ESP prints R,1 every 5s by default; give margin)

# Sender timeout (seconds) - should match your ESP behavior + ping/pong grace
SENDER_TIMEOUT = 180

# If True: treat "port open" as receiver online even without R,1 frames.
# Recommended: False (more accurate). Set True during transition.
PORT_OPEN_COUNTS_AS_ONLINE = False

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ===============================================================
#   REGEX PARSERS
# ===============================================================
# New CSV protocol
csv_state_regex   = re.compile(r'^S,(\d+),(\d+),(\d+),(\d+)$')     # S,sid,motion,ramp,seq
csv_online_regex  = re.compile(r'^O,(\d+),(0|1)$')                # O,sid,online
csv_receiver_regex = re.compile(r'^R,(0|1)$')                     # R,1

# Legacy verbose protocol (kept for backward compatibility)
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
        Simulated Receiver behavior:
        • Sends receiver heartbeat frames: R,1
        • Sends state frames for 10 seconds
        • Then completely silent for 12 seconds
        • Repeats forever
        • Works with DebugInjection buffer
        """

        def __init__(self):
            self.phase = "sending"
            self.last_phase_change = time.time()
            self.idx = 0

            self.frames = [
                b"R,1\n",
                b"O,1,1\n",
                b"S,1,2,2,10\n",
                b"S,2,1,1,11\n",
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

            # Active sending window
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
            except Exception:
                continue

        raise IOError("No serial ports found")

    # ===========================================================
    #   THREAD-SAFE UI HELPERS
    # ===========================================================
    def ui_set_receiver_online(online: bool):
        QMetaObject.invokeMethod(
            receiver_status_fn.__self__,
            "set_receiver_status",
            Qt.QueuedConnection,
            Q_ARG(bool, online)
        )

    def ui_set_sender_offline(sid: int, offline: bool):
        QMetaObject.invokeMethod(
            mark_offline_fn.__self__,
            "set_simulator_offline",
            Qt.QueuedConnection,
            Q_ARG(int, sid),
            Q_ARG(bool, offline)
        )

    def ui_update_sender_state(sid: int, motion: int, ramp: int):
        QMetaObject.invokeMethod(
            update_sim_fn.__self__,
            "update_simulator_state",
            Qt.QueuedConnection,
            Q_ARG(int, sid),
            Q_ARG(int, motion),
            Q_ARG(int, ramp)
        )

    # ===========================================================
    #   SERIAL THREAD
    # ===========================================================
    def reader_thread():
        ser = None
        receiver_last_seen = 0.0
        receiver_online = False

        # Sender last-seen timestamps
        last_seen = {}  # sid -> epoch seconds

        # Optional: if you want to suppress repeated offline UI calls
        sender_offline_state = {sid: True for sid in sim_cards}  # assume offline until we see data

        try:
            ser = open_port(SERIAL_PORT)

            # If you choose to treat "port open" as online
            if PORT_OPEN_COUNTS_AS_ONLINE:
                receiver_online = True
                receiver_last_seen = time.time()
                ui_set_receiver_online(True)
            else:
                # Start as offline until we get R,1 (or any valid receiver-origin frames if you prefer)
                receiver_online = False
                ui_set_receiver_online(False)

            while _RUN_FLAG:
                raw_bytes = ser.readline()
                raw = raw_bytes.decode(errors="replace").strip() if raw_bytes else ""

                now = time.time()

                # ---------------------------------------------------
                # Receiver online/offline check (based on R,1 frames)
                # ---------------------------------------------------
                # If we haven't seen receiver heartbeat recently, mark receiver offline.
                if receiver_online and (now - receiver_last_seen) > RECEIVER_HEARTBEAT_TIMEOUT:
                    receiver_online = False
                    ui_set_receiver_online(False)

                # If blank line, continue (silence)
                if not raw:
                    # Still check sender timeouts even if silent
                    for sim_id in sim_cards:
                        last = last_seen.get(sim_id, 0.0)
                        if last > 0 and (now - last) > SENDER_TIMEOUT:
                            if sender_offline_state.get(sim_id) is not True:
                                sender_offline_state[sim_id] = True
                                ui_set_sender_offline(sim_id, True)
                    continue

                # ---------------------------------------------------
                # Parse NEW CSV protocol
                # ---------------------------------------------------
                m_recv = csv_receiver_regex.match(raw)
                if m_recv:
                    alive = bool(int(m_recv.group(1)))
                    receiver_last_seen = now
                    if alive and not receiver_online:
                        receiver_online = True
                        ui_set_receiver_online(True)
                    elif (not alive) and receiver_online:
                        receiver_online = False
                        ui_set_receiver_online(False)
                    continue

                m_online = csv_online_regex.match(raw)
                if m_online:
                    sid = int(m_online.group(1))
                    online = bool(int(m_online.group(2)))

                    # Forced disconnect (debug panel)
                    if serial_debug.disconnect_flags.get(sid, False):
                        continue

                    # Seeing O frames implies receiver is alive too
                    receiver_last_seen = now
                    if not receiver_online:
                        receiver_online = True
                        ui_set_receiver_online(True)

                    if online:
                        last_seen[sid] = now
                        if sender_offline_state.get(sid) is not False:
                            sender_offline_state[sid] = False
                            ui_set_sender_offline(sid, False)
                    else:
                        if sender_offline_state.get(sid) is not True:
                            sender_offline_state[sid] = True
                            ui_set_sender_offline(sid, True)
                    continue

                m_state = csv_state_regex.match(raw)
                if m_state:
                    sid = int(m_state.group(1))
                    mot = int(m_state.group(2))
                    ramp = int(m_state.group(3))
                    # seq = int(m_state.group(4))  # available if you want it

                    # Forced disconnect (debug panel)
                    if serial_debug.disconnect_flags.get(sid, False):
                        continue

                    # Seeing S frames implies receiver is alive too
                    receiver_last_seen = now
                    if not receiver_online:
                        receiver_online = True
                        ui_set_receiver_online(True)

                    last_seen[sid] = now
                    if sender_offline_state.get(sid) is not False:
                        sender_offline_state[sid] = False
                        ui_set_sender_offline(sid, False)

                    ui_update_sender_state(sid, mot, ramp)
                    continue

                # ---------------------------------------------------
                # Backward compatibility: Parse legacy verbose lines
                # ---------------------------------------------------
                m_legacy = data_regex.match(raw) or heartbeat_regex.match(raw)
                if m_legacy:
                    sid = int(m_legacy.group(1))
                    ramp = int(m_legacy.group(2))
                    mot = int(m_legacy.group(3))
                    # seq = int(m_legacy.group(4))

                    if serial_debug.disconnect_flags.get(sid, False):
                        continue

                    receiver_last_seen = now
                    if not receiver_online:
                        receiver_online = True
                        ui_set_receiver_online(True)

                    last_seen[sid] = now
                    if sender_offline_state.get(sid) is not False:
                        sender_offline_state[sid] = False
                        ui_set_sender_offline(sid, False)

                    ui_update_sender_state(sid, mot, ramp)
                    continue

                # Unknown line -> ignore
                continue

        except Exception as exc:
            logger.error(f"Serial worker error: {exc}")
            receiver_online = False
            ui_set_receiver_online(False)

        finally:
            if ser and hasattr(ser, "is_open") and ser.is_open:
                try:
                    ser.close()
                    logger.info("Serial port closed.")
                except Exception:
                    pass

            # Final offline state
            ui_set_receiver_online(False)

    # ===========================================================
    #   START THREAD
    # ===========================================================
    threading.Thread(target=reader_thread, daemon=True).start()