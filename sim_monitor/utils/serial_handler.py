import threading
import logging
import time
import re

try:
    import ubinascii as binascii
except ImportError:
    import binascii

try:
    import serial
except ImportError:
    serial = None  # or mock if needed

DEBUG_MODE = False
SERIAL_PORT = "COM10"
BAUD_RATE = 115200

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)

# Regex for data lines, e.g.:
# [DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54
data_regex = re.compile(
    r'^\[DATA\]\s+Received from Sender ID\s+(\d+):\s+RampState=(\d+),\s+MotionState=(\d+),\s+Seq=(\d+)$'
)

# Regex for heartbeat lines, e.g.:
# [HEARTBEAT] Received from Sender ID 1, Seq=99
heartbeat_regex = re.compile(
    r'^\[HEARTBEAT\]\s+Received from Sender ID\s+(\d+),\s+Seq=(\d+)$'
)

def update_simulators(root, simulators, add_simulator,
                      serial_port=SERIAL_PORT, baud_rate=BAUD_RATE):
    """
    Reads ASCII lines from the receiver (which prints lines like:
      [DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54
    or
      [HEARTBEAT] Received from Sender ID 1, Seq=99
    Then parse them and update the GUI simulators.
    """

    class MockSerial:
        """Mock for debug mode."""
        def __init__(self):
            self.lines = [
                b"[DATA] Received from Sender ID 1: RampState=2, MotionState=1, Seq=54\n",
                b"[HEARTBEAT] Received from Sender ID 1, Seq=99\n",
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

                        # Check for [DATA]
                        match_data = data_regex.match(line_str)
                        if match_data:
                            sender_id_val = int(match_data.group(1))
                            ramp_state = int(match_data.group(2))
                            motion_state = int(match_data.group(3))
                            seq = int(match_data.group(4))

                            logger.info(f"Parsed DATA => ID={sender_id_val}, Ramp={ramp_state}, Motion={motion_state}, Seq={seq}")

                            # If we haven't seen this device, add it
                            if sender_id_val not in simulators:
                                root.after(0, add_simulator, sender_id_val)
                            # Update simulator with ramp/motion
                            root.after(0, simulators[sender_id_val].update_state, ramp_state, motion_state)
                            continue

                        # Check for [HEARTBEAT]
                        match_heart = heartbeat_regex.match(line_str)
                        if match_heart:
                            sender_id_val = int(match_heart.group(1))
                            seq = int(match_heart.group(2))
                            logger.info(f"Parsed HEARTBEAT => ID={sender_id_val}, Seq={seq}")
                            continue

                        # If neither matched
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

    logger.info("🔧 Debug mode enabled." if DEBUG_MODE else "🚀 Running in live mode.")
    # Spawn the worker thread once
    t = threading.Thread(target=serial_worker, args=(root, simulators, add_simulator), daemon=True)
    t.start()
