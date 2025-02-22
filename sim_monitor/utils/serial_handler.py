import threading
import logging
import time
import re

try:
    import serial
except ImportError:
    serial = None  # or mock if needed

DEBUG_MODE = False
SERIAL_PORT = "COM10"
BAUD_RATE = 115200

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(message)s")

# === Regex for [DATA] lines ===
# e.g.: [DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54
data_regex = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$'
)

# === Regex for [HEARTBEAT] lines (with ramp/motion) ===
# e.g.: [HEARTBEAT] Received from Sender ID 1: RampState=2, MotionState=1, Seq=99
heartbeat_regex = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$'
)

# Track each sender's status for offline detection
active_senders = {}

def update_simulators(root, simulators, add_simulator,
                      serial_port=SERIAL_PORT, baud_rate=BAUD_RATE):
    """
    Reads ASCII lines from the ESP32 receiver in a separate thread,
    updating simulators with ramp/motion states. Also implements
    offline detection with retries.
    """

    class MockSerial:
        """Mock for debug mode."""
        def __init__(self):
            self.lines = [
                b"[DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54\n",
                b"[HEARTBEAT] Received from Sender ID 1: RampState=2, MotionState=1, Seq=99\n",
                b"[DATA] Received from Sender ID 2: RampState=0, MotionState=2, Seq=100\n",
            ]
            self.index = 0

        def readline(self):
            if self.index < len(self.lines):
                line = self.lines[self.index]
                self.index += 1
                time.sleep(2)
                return line
            return b''

        @property
        def is_open(self):
            return True

        def close(self):
            logger.info("Mock serial closed.")

    def serial_worker(root, simulators, add_simulator):
        """Thread that reads lines from the serial port and parses them."""
        try:
            if DEBUG_MODE or serial is None:
                ser = MockSerial()
                logger.info("Using MockSerial (Debug Mode).")
            else:
                ser = serial.Serial(serial_port, baud_rate, timeout=1)
                logger.info(f"Serial port open: {ser.is_open}")

            while True:
                try:
                    line_bytes = ser.readline()
                    if line_bytes:
                        line_str = line_bytes.decode('utf-8', errors='replace').strip()
                        logger.debug(f"Raw line: {line_str}")

                        # === Check [DATA] lines ===
                        match_data = data_regex.match(line_str)
                        if match_data:
                            sender_id_val = int(match_data.group(1))
                            ramp_state = int(match_data.group(2))
                            motion_state = int(match_data.group(3))
                            seq = int(match_data.group(4))

                            logger.info(f"Parsed DATA => ID={sender_id_val}, "
                                        f"Ramp={ramp_state}, Motion={motion_state}, Seq={seq}")

                            # If new device, add it
                            if sender_id_val not in simulators:
                                root.after(0, add_simulator, sender_id_val)

                            # Mark device as active
                            _mark_device_active(sender_id_val)

                            # Update simulator ramp/motion
                            root.after(0, simulators[sender_id_val].update_state, ramp_state, motion_state)
                            continue

                        # === Check [HEARTBEAT] lines (with ramp/motion) ===
                        match_heart = heartbeat_regex.match(line_str)
                        if match_heart:
                            sender_id_val = int(match_heart.group(1))
                            ramp_state = int(match_heart.group(2))
                            motion_state = int(match_heart.group(3))
                            seq = int(match_heart.group(4))

                            logger.info(f"Parsed HEARTBEAT => ID={sender_id_val}, "
                                        f"Ramp={ramp_state}, Motion={motion_state}, Seq={seq}")

                            # Mark device as active
                            _mark_device_active(sender_id_val)

                            # If new device, add it
                            if sender_id_val not in simulators:
                                root.after(0, add_simulator, sender_id_val)

                            # Update simulator ramp/motion on heartbeat
                            root.after(0, simulators[sender_id_val].update_state, ramp_state, motion_state)
                            continue

                        # Otherwise, warn
                        if line_str:
                            logger.warning(f"Line didn't match expected format: {line_str}")
                    else:
                        # No data read
                        pass

                except Exception as e:
                    logger.error(f"Error during serial read: {e}")
                    time.sleep(0.5)

        except Exception as e:
            logger.error(f"Unhandled error in serial_worker: {e}")
        finally:
            if 'ser' in locals() and getattr(ser, 'is_open', False):
                ser.close()
                logger.info("Serial port closed.")

    def _mark_device_active(sender_id_val):
        """Reset the offline counters for this sender."""
        now = time.time()
        if sender_id_val not in active_senders:
            active_senders[sender_id_val] = {
                'last_heartbeat': now,
                'retry_count': 0,
                'is_offline': False
            }
        else:
            info = active_senders[sender_id_val]
            info['last_heartbeat'] = now
            info['retry_count'] = 0
            if info['is_offline']:
                # Mark back online
                info['is_offline'] = False
                logger.info(f"Sender {sender_id_val} is back ONLINE")
                # If the simulator is offline, set it to online
                if sender_id_val in simulators:
                    root.after(0, simulators[sender_id_val].set_offline, False)

    def _set_simulator_disconnected(sid):
        """Mark the simulator as offline in the UI."""
        sim = simulators.get(sid)
        if sim:
            sim.set_offline(True)

    def offline_checker():
        """Check every 5s if any sender is offline after missing 3 intervals of 30s."""
        now = time.time()
        for sid, info in list(active_senders.items()):
            if not info['is_offline']:
                elapsed = now - info['last_heartbeat']
                if elapsed > 30:
                    info['retry_count'] += 1
                    logger.warning(f"No heartbeat from ID={sid} for {int(elapsed)}s, retry_count={info['retry_count']}")
                    # Reset last_heartbeat so we don't spam every second
                    info['last_heartbeat'] = now

                    if info['retry_count'] >= 3:
                        info['is_offline'] = True
                        logger.warning(f"Sender {sid} is OFFLINE after 3 missed intervals")

                        # Mark simulator disconnected
                        if sid in simulators:
                            root.after(0, _set_simulator_disconnected, sid)

        # Schedule next check
        root.after(5000, offline_checker)

    def start_offline_monitor():
        """Start the offline checker loop."""
        root.after(5000, offline_checker)

    logger.info("Starting serial_worker thread & offline checker...")
    t = threading.Thread(target=serial_worker, args=(root, simulators, add_simulator), daemon=True)
    t.start()

    # Start the offline monitor
    start_offline_monitor()
