import threading
import random
import serial
import time

DEBUG_MODE = False  # Toggle debug mode for testing without serial input

def update_simulators(root, simulators, serial_port='/dev/ttyUSB0', baud_rate=115200):
    """
    Updates the state of simulators based on either debug-mode random data or serial input.
    This function uses threading to avoid blocking the GUI.
    """
    def serial_worker():
        """Worker function to handle serial communication in a separate thread."""
        try:
            # Open the serial port
            ser = serial.Serial(serial_port, baud_rate, timeout=1)
            print(f"Serial port open: {ser.is_open}")

            while True:
                if ser.in_waiting > 0:
                    data = ser.readline().decode('utf-8', errors='ignore').strip()
                    print(f"Raw serial data: {data}")  # Debugging log for raw data

                    # Parse the data (Expected format: "sim_name,ramp_state,motion_state,status")
                    parts = data.split(",")
                    if len(parts) == 4:
                        sim_name, ramp_state, motion_state, status = parts
                        ramp_state = int(ramp_state)
                        motion_state = int(motion_state)
                        status = int(status)

                        # Update the simulator state that matches the received name
                        for sim in simulators:
                            if sim.name == sim_name:
                                # Use `root.after` to safely update the GUI
                                root.after(0, sim.update_state, ramp_state, motion_state, status)
                                break
                    else:
                        print(f"Invalid data format: {data}")  # Log invalid data format
                else:
                    time.sleep(0.1)  # Small delay to prevent busy-waiting
        except Exception as e:
            print(f"Serial communication error: {e}")

    if DEBUG_MODE:
        # Simulate random data updates in debug mode
        def debug_worker():
            while True:
                for sim in simulators:
                    ramp_state = random.randint(0, 2)  # 0: Motion, 1: Up, 2: Down
                    motion_state = random.randint(1, 2)  # 1: Sim Down, 2: Sim Up
                    status = random.randint(0, 1)  # 0: No Data, 1: Connected
                    root.after(0, sim.update_state, ramp_state, motion_state, status)
                time.sleep(2)  # Adjust delay for debug updates

        threading.Thread(target=debug_worker, daemon=True).start()
    else:
        # Start the serial worker thread
        threading.Thread(target=serial_worker, daemon=True).start()