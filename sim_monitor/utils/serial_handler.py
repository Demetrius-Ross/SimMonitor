import threading
import random
import serial
import time
import logging

DEBUG_MODE = True  # Toggle debug mode for testing without serial input
serial_port = 'COM5'
baud_rate = 115200

logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO)
logger = logging.getLogger(__name__)

def update_simulators(root, simulators, serial_port=serial_port, baud_rate=baud_rate):
    """
    Updates the state of simulators based on either debug-mode random data or serial input.
    This function uses threading to avoid blocking the GUI.
    """
    class MockSerial:
        """Mock Serial class for debugging purposes."""
        def __init__(self):
            self.in_waiting = 1
            self.simulators = ["ERJ-24", "EC-135", "PC-12"]
            self.current_states = {
                sim: {"ramp_state": 0, "motion_state": 1, "status": 1}
                for sim in self.simulators
            }
            self.index = 0

        def readline(self):
            time.sleep(0.1)

            # Cycle through each simulator and randomly update its state
            for sim in self.simulators:
                self.current_states[sim]["ramp_state"] = random.randint(0, 2)  # 0: Motion, 1: Up, 2: Down
                self.current_states[sim]["motion_state"] = random.randint(1, 2)  # 1: Sim Down, 2: Sim Up
                self.current_states[sim]["status"] = random.randint(0, 1)  # 0: No Data, 1: Connected

            # Format the message for the current simulator
            simulator = self.simulators[self.index]
            state = self.current_states[simulator]
            self.index = (self.index + 1) % len(self.simulators)

            message = f"<{simulator},{state['ramp_state']},{state['motion_state']},{state['status']}>"
            return message.encode('utf-8')

        def close(self):
            logger.info("Mock serial closed.")

        @property
        def is_open(self):
            return True

    def serial_worker():
        """Worker function to handle serial communication in a separate thread."""
        try:
            # Use MockSerial in debug mode; otherwise, open the actual serial port
            ser = MockSerial() if DEBUG_MODE else serial.Serial(serial_port, baud_rate, timeout=0.1)
            logger.info(f"Serial port open: {ser.is_open}")

            while True:
                try:
                    if ser.in_waiting > 0:
                        # Read and decode data from the serial port
                        data = ser.readline().decode('utf-8', errors='ignore').strip()
                        logger.debug(f"Raw serial data: {data}")

                        # Process data with delimiters
                        if data.startswith('<') and data.endswith('>'):
                            data = data[1:-1]  # Remove delimiters
                            parts = data.split(",")
                            if len(parts) == 4:
                                sim_name, ramp_state, motion_state, status = parts
                                try:
                                    # Convert string values to integers
                                    ramp_state, motion_state, status = map(int, (ramp_state, motion_state, status))

                                    # Match simulator name and update its state
                                    for sim in simulators:
                                        if sim.name == sim_name:
                                            root.after(0, sim.update_state, ramp_state, motion_state, status)
                                            break
                                    else:
                                        logger.warning(f"Unrecognized simulator name: {sim_name}")
                                except ValueError as e:
                                    logger.error(f"Error parsing data: {data} -> {e}")
                            else:
                                logger.warning(f"Invalid data format: {data}")
                        else:
                            logger.warning(f"Discarded non-delimited data: {data}")
                    else:
                        time.sleep(0.05)  # Prevent busy waiting
                except Exception as e:
                    logger.error(f"Error during serial read: {e}")
                    time.sleep(0.1)
        except serial.SerialException as e:
            logger.error(f"Serial communication error: {e}")
        except Exception as e:
            logger.error(f"Unhandled error: {e}")
        finally:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                logger.info("Serial port closed.")

    if DEBUG_MODE:
        logger.info("Debug mode enabled. Using mock serial input.")
    else:
        logger.info("Running in live mode. Using actual serial input.")

    # Start the worker thread
    threading.Thread(target=serial_worker, daemon=True).start()
