import threading
import logging
import time
import re

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None  # or a mock
    # If you want the scanning logic to work, install pyserial on your Pi:
    #   pip install pyserial

DEBUG_MODE = False  # Set to True if you want to use the MockSerial
SERIAL_PORT = "/dev/ttyUSB0"  # The preferred/initial port to try
BAUD_RATE = 115200

chosen_port = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(message)s")

# Example regex patterns for your line-based approach
data_regex = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$'
)
heartbeat_regex = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$'
)

# Example structure for offline detection
active_senders = {}

def update_simulators(root, simulators, add_simulator,
                      serial_port=SERIAL_PORT, baud_rate=BAUD_RATE):
    """
    Reads ASCII lines from the ESP32 receiver in a separate thread,
    updating simulators with ramp/motion states. Also implements
    offline detection with retries.

    1) Attempt to open 'serial_port' (e.g. "/dev/ttyUSB0").
    2) If that fails, scan all available USB ports ("/dev/ttyUSB1", etc.).
    3) If no port is found, raise an exception.
    """

    class MockSerial:
        """Mock for debug mode, simulating incoming lines."""
        def __init__(self):
            self.lines = [
                b"[DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54\n",
                b"[HEARTBEAT] Received from Sender ID 1: RampState=2, MotionState=1, Seq=99\n",
                b"[DATA] Received from Sender ID 2: RampState=0, MotionState=2, Seq=100\n",
                b"[HEARTBEAT] Received from Sender ID 2: RampState=2, MotionState=1, Seq=99\n",
                # ... add more lines if desired
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

    def open_any_serial_port(preferred_port, baud):
        """
        1) Try the user-specified 'preferred_port'.
        2) If that fails, scan all serial ports (e.g. /dev/ttyUSB*, COMx, etc.)
           and pick the first one that works.
        Returns a serial object or raises an exception if none found.
        """
        global chosen_port
        if DEBUG_MODE or serial is None:
            logger.info("Using MockSerial (Debug Mode).")
            return MockSerial()

        # 1) Try preferred_port first
        try:
            ser = serial.Serial(preferred_port, baud, timeout=1)
            logger.info(f"Serial port open: {ser.is_open} on {preferred_port}")
            if ser.is_open:
                chosen_port = ser.port
                return ser
        except Exception as e:
            logger.warning(f"Failed to open preferred port {preferred_port}: {e}")

        # 2) Scan all ports
        logger.info("Scanning available serial ports...")
        available_ports = list(serial.tools.list_ports.comports())
        for p in available_ports:
            try:
                ser = serial.Serial(p.device, baud, timeout=1)
                logger.info(f"Opened fallback port: {p.device}")
                chosen_port = ser.port
                return ser
            except Exception as e:
                logger.warning(f"Failed on {p.device}: {e}")

        # If we get here, no port was opened
        raise IOError("No valid serial ports found.")

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

    def serial_worker(root, simulators, add_simulator):
        """Thread that reads lines from the dynamically chosen serial port and parses them."""
        try:
            ser = open_any_serial_port(serial_port, baud_rate)

            while True:
                try:
                    line_bytes = ser.readline()
                    if line_bytes:
                        line_str = line_bytes.decode('utf-8', errors='replace').strip()
                        logger.debug(f"Raw line: {line_str}")

                        # Check [DATA]
                        match_data = data_regex.match(line_str)
                        if match_data:
                            sender_id_val = int(match_data.group(1))
                            ramp_state = int(match_data.group(2))
                            motion_state = int(match_data.group(3))
                            seq = int(match_data.group(4))

                            logger.info(f"Parsed DATA => ID={sender_id_val}, Ramp={ramp_state}, Motion={motion_state}, Seq={seq}")

                            # If new device, add it
                            if sender_id_val not in simulators:
                                root.after(0, add_simulator, sender_id_val)

                            # Mark device as active
                            _mark_device_active(sender_id_val)

                            # Update simulator ramp/motion
                            root.after(0, simulators[sender_id_val].update_state, ramp_state, motion_state)
                            continue

                        # Check [HEARTBEAT]
                        match_heart = heartbeat_regex.match(line_str)
                        if match_heart:
                            sender_id_val = int(match_heart.group(1))
                            ramp_state = int(match_heart.group(2))
                            motion_state = int(match_heart.group(3))
                            seq = int(match_heart.group(4))

                            logger.info(f"Parsed HEARTBEAT => ID={sender_id_val}, Ramp={ramp_state}, Motion={motion_state}, Seq={seq}")

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

    logger.info("Starting serial_worker thread & offline checker...")
    t = threading.Thread(target=serial_worker, args=(root, simulators, add_simulator), daemon=True)
    t.start()

    # Start the offline monitor
    start_offline_monitor()
