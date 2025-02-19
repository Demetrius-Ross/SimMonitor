import threading
import serial
import time
import struct  # For unpacking binary data
import logging
import random

DEBUG_MODE = True  # Set to True for mock serial input
SERIAL_PORT = "/dev/ttyUSB0"  # Change as needed
BAUD_RATE = 115200

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger(__name__)

# === Define Packet Format ===
PACKET_FORMAT = ">BBHH"  # [Device ID (1B), Message Type (1B), Ramp State (2B), Motion State (2B)]
PACKET_SIZE = struct.calcsize(PACKET_FORMAT)  # Expected packet size (6 bytes)

def update_simulators(root, simulators, add_simulator, serial_port=SERIAL_PORT, baud_rate=BAUD_RATE):
    """
    Updates the state of simulators based on either debug-mode random data or serial input.
    Runs in a separate thread to avoid blocking the GUI.
    """

    class MockSerial:
        """Mock Serial class for debugging purposes (if DEBUG_MODE is enabled)."""
        def __init__(self):
            self.sim_ids = [0x01, 0x02, 0x03]  # Example device IDs
            self.index = 0
            self.in_waiting = 1  # Simulate available data
            self.current_states = {sim_id: (0, 1) for sim_id in self.sim_ids}  # Store state per simulator

        def readline(self):
            """Simulate new state updates every 3-7 seconds."""
            time.sleep(random.uniform(10, 15))  # ✅ Random delay before switching states

            sim_id = self.sim_ids[self.index]

            # Randomly update ramp and motion states
            ramp_state = random.choice([0, 1, 2])  # 0 = In Motion, 1 = Ramp Up, 2 = Ramp Down
            motion_state = random.choice([1, 2])  # 1 = Sim Down, 2 = Sim Up
            message_type = 0xA1  # Data message

            self.current_states[sim_id] = (ramp_state, motion_state)
            self.index = (self.index + 1) % len(self.sim_ids)

            # Pack message into binary format
            message = struct.pack(PACKET_FORMAT, sim_id, message_type, ramp_state, motion_state)
            
            logger.info(f"[DEBUG] Mock Update - ID: {sim_id}, Ramp: {ramp_state}, Motion: {motion_state}")
            return message

        def close(self):
            logger.info("Mock serial closed.")

        @property
        def is_open(self):
            return True

    def serial_worker(root, simulators, add_simulator):
        """Worker function to read ESP-NOW messages from serial and update UI."""
        try:
            ser = MockSerial() if DEBUG_MODE else serial.Serial(serial_port, baud_rate, timeout=0.1)
            #logger.info(f"✅ Serial port open: {ser.is_open}")

            while True:
                try:
                    #logger.debug("[DEBUG] Waiting for serial data...")

                    raw_data = ser.readline()
                    #logger.debug(f"[DEBUG] Raw Serial Data Received: {raw_data.hex() if raw_data else 'None'}")

                    if len(raw_data) == PACKET_SIZE:
                        device_id, msg_type, ramp_state, motion_state = struct.unpack(PACKET_FORMAT, raw_data)
                        logger.info(f"📩 [RECEIVED] ID={device_id}, Ramp={ramp_state}, Motion={motion_state}")

                        if msg_type == 0xA1:  # Data Message
                            if device_id not in simulators:
                                root.after(0, add_simulator, device_id)

                            root.after(0, simulators[device_id].update_state, ramp_state, motion_state, 1)
                    else:
                        logger.warning("⚠️ Incomplete or invalid packet received, ignoring.")

                    time.sleep(0.05)

                except Exception as e:
                    logger.error(f"❌ Error during serial read: {e}")
                    time.sleep(0.1)

        except serial.SerialException as e:
            logger.error(f"❌ Serial communication error: {e}")
        except Exception as e:
            logger.error(f"❌ Unhandled error: {e}")
        finally:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                logger.info("✅ Serial port closed.")

    if DEBUG_MODE:
        logger.info("🔧 Debug mode enabled. Using mock serial input.")
    else:
        logger.info("🚀 Running in live mode. Using actual serial input.")

    # ✅ **Fix: Pass `root`, `simulators`, and `add_simulator` correctly**
    threading.Thread(target=serial_worker, args=(root, simulators, add_simulator), daemon=True).start()
