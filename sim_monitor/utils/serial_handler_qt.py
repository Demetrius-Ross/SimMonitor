# serial_handler_qt.py
"""
Qt-friendly Serial Monitor for the Sim-Monitor GUI
--------------------------------------------------
• Real serial reading when DEBUG_MODE=False
• Fully simulated ESP-NOW sender behavior when DEBUG_MODE=True
• Inject simulated disconnects for senders (Debug Panel)
• Receiver ESP32 online/offline detection
• Safe Qt-thread callback signaling
"""

import logging, threading, time, re
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG

try:
    import serial, serial.tools.list_ports
except ImportError:
    serial = None


# ===============================================================
#   GLOBAL DEBUG INJECTION ENGINE
# ===============================================================
class DebugInjection:
    """
    Handles:
    • Per-SIM disconnect toggling
    • Inject fake DATA / fake HEARTBEAT frames
    • Buffering injected raw lines
    """

    def __init__(self):
        self.disconnect_flags = {}      # sid → True/False
        self._inject_buffer = []        # queued injected lines

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


# Global instance used by GUI
serial_debug = DebugInjection()


# ===============================================================
#   CONFIG & REGEX
# ===============================================================
DEBUG_MODE = False
SERIAL_PORT = "COM3"
BAUD_RATE = 115200
READ_TIMEOUT = 1.0

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

data_regex = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),'
    r'\s+MotionState=(\d+),\s+Seq=(\d+)$'
)
heartbeat_regex = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),'
    r'\s+MotionState=(\d+),\s+Seq=(\d+)$'
)


# ===============================================================
#   PUBLIC FUNCTIONS CALLED BY MAIN GUI
# ===============================================================
def set_debug_mode(enabled: bool):
    global DEBUG_MODE
    DEBUG_MODE = enabled
    logger.info(f"Serial debug mode set to: {'DEBUG' if enabled else 'LIVE'}")


def stop_serial_thread():
    global _RUN_FLAG
    _RUN_FLAG = False


# ===============================================================
#   MAIN THREAD START
# ===============================================================
def start_serial_thread(
    sim_cards: dict,
    *,
    update_sim_fn,
    mark_offline_fn,
    receiver_status_fn
):
    """
    sim_cards:           { sim_id: SimulatorCard }
    update_sim_fn:       MainWindow.update_simulator_state
    mark_offline_fn:     MainWindow.set_simulator_offline
    receiver_status_fn:  MainWindow.set_receiver_status
    """
    global _RUN_FLAG
    _RUN_FLAG = True

    # ===========================================================
    #   DEBUG MODE — EMULATED SERIAL SOURCE (Mock ESP-NOW)
    # ===========================================================
    class MockSerial:
        """
        Behavior:
        • Sim 1 & 2 send frames for 10 seconds
        • Silence for 12 seconds (simulate full disconnect)
        • Repeat
        • DebugPanel can override with forced dropouts or inject frames
        """

        def __init__(self):
            self.phase = "sending"
            self.last_phase_change = time.time()
            self.idx = 0

            # Sample simulated frames
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
            now = time.time()

            # Priority to injected frames
            if serial_debug._inject_buffer:
                return serial_debug._inject_buffer.pop(0)

            # Phase 1 — active send for 10s
            if self.phase == "sending":
                if now - self.last_phase_change < 10:
                    time.sleep(1)
                    line = self.frames[self.idx % len(self.frames)]
                    self.idx += 1
                    return line
                else:
                    self.phase = "silent"
                    self.last_phase_change = now
                    return b""

            # Phase 2 — silent for 12s to simulate disconnect
            elif self.phase == "silent":
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
    def open_any_serial_port(preferred: str, baud: int):
        # Debug mode forces mock serial
        if DEBUG_MODE or serial is None:
            logger.info("Using MockSerial (DEBUG mode)")
            return MockSerial()

        # Try preferred device
        try:
            if preferred:
                s = serial.Serial(preferred, baud, timeout=READ_TIMEOUT)
                logger.info(f"Opened preferred port {preferred}")
                return s
        except Exception as exc:
            logger.warning(f"Preferred port failed: {exc}")

        # Auto-scan all ports
        logger.info("Scanning serial ports…")
        for p in serial.tools.list_ports.comports():
            try:
                s = serial.Serial(p.device, baud, timeout=READ_TIMEOUT)
                logger.info(f"Opened {p.device}")
                return s
            except Exception:
                continue

        raise IOError("No serial ports available")


    # ===========================================================
    #   SERIAL READER THREAD
    # ===========================================================
    def reader_thread():
        ser = None

        try:
            ser = open_any_serial_port(SERIAL_PORT, BAUD_RATE)

            # Notify GUI that receiver is online
            QMetaObject.invokeMethod(
                receiver_status_fn.__self__,
                "set_receiver_status",
                Qt.QueuedConnection,
                Q_ARG(bool, True)
            )

            # Last-seen timestamps for each sender
            last_seen = {}
            OFFLINE_TIMEOUT = 10  # seconds

            # Track silence time for receiver
            last_any_rx = time.time()

            while _RUN_FLAG:
                raw_bytes = ser.readline()
                raw = raw_bytes.decode(errors="replace").strip()
                now = time.time()

                # =========================
                #   Receiver silence watchdog
                # =========================
                if ser and hasattr(ser, "is_open") and ser.is_open:
                    QMetaObject.invokeMethod(
                        receiver_status_fn.__self__,
                        "set_reciever_status",
                        Qt.QueuedConnection,
                        Q_ARG(bool, True)
                    )

                # =========================
                #   PROCESS ANY SERIAL LINE
                # =========================
                if raw:
                    logger.debug(f"RX: {raw}")

                    m = data_regex.match(raw) or heartbeat_regex.match(raw)
                    if m:
                        sid = int(m.group(1))
                        ramp = int(m.group(2))
                        mot = int(m.group(3))

                        # Debug forced disconnect
                        if serial_debug.disconnect_flags.get(sid, False):
                            continue

                        # Update sender last seen timestamp
                        last_seen[sid] = now

                        # Mark sender ONLINE
                        QMetaObject.invokeMethod(
                            mark_offline_fn.__self__,
                            "set_simulator_offline",
                            Qt.QueuedConnection,
                            Q_ARG(int, sid),
                            Q_ARG(bool, False)
                        )

                        # Update GUI sim state
                        QMetaObject.invokeMethod(
                            update_sim_fn.__self__,
                            "update_simulator_state",
                            Qt.QueuedConnection,
                            Q_ARG(int, sid),
                            Q_ARG(int, mot),
                            Q_ARG(int, ramp)
                        )

                # =========================
                #   SENDER OFFLINE CHECK
                # =========================
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

            # Receiver OFFLINE
            QMetaObject.invokeMethod(
                receiver_status_fn.__self__,
                "set_receiver_status",
                Qt.QueuedConnection,
                Q_ARG(bool, False)
            )

        finally:
            # Close port safely
            if ser and hasattr(ser, "is_open") and ser.is_open:
                ser.close()
                logger.info("Serial port closed.")

            # Receiver OFFLINE (final)
            QMetaObject.invokeMethod(
                receiver_status_fn.__self__,
                "set_receiver_status",
                Qt.QueuedConnection,
                Q_ARG(bool, False)
            )


    # ===========================================================
    #   LAUNCH THREAD
    # ===========================================================
    threading.Thread(target=reader_thread, daemon=True).start()