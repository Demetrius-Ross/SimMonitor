import random
import serial
import time

DEBUG_MODE = True  # Toggle debug mode for testing without serial input

# Serial port configuration (update the port name as needed)
SERIAL_PORT = "/dev/ttyUSB0"  # Correct the port if necessary
BAUD_RATE = 115200
TIMEOUT = 1  # Timeout for serial read in seconds

last_update_time = None  # Global variable to track the last update time


def update_simulators(root, simulators):
    """
    Updates the state of simulators based on either debug-mode random data or serial input.
    """
    global last_update_time
    current_time = time.time()  # Use time.time() for precise time measurement
    delay = 2  # Delay in seconds for debug mode

    # Check if enough time has passed since the last update
    if last_update_time and current_time - last_update_time < delay:
        root.after(100, lambda: update_simulators(root, simulators))  # Reschedule the next update
        return

    last_update_time = current_time  # Update the last update time

    if DEBUG_MODE:
        # Generate random data for testing purposes
        for sim in simulators:
            ramp_state = random.randint(0, 2)  # 0: Motion, 1: Up, 2: Down
            motion_state = random.randint(1, 2)  # 1: Sim Down, 2: Sim Up
            status = random.randint(0, 1)  # 0: No Data, 1: Connected
            sim.update_state(ramp_state, motion_state, status)
    else:
        try:
            # Open the serial port
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)

            # Read serial data if available
            if ser.in_waiting > 0:
                data = ser.readline().decode("utf-8").strip()  # Read and decode serial data
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
                            sim.update_state(ramp_state, motion_state, status)
                            break
                else:
                    print(f"Invalid data format: {data}")  # Log invalid data format

            ser.close()  # Close the serial port after reading
        except serial.SerialException as e:
            print(f"Serial communication error: {e}")
        except ValueError as e:
            print(f"Data conversion error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    # Schedule the next update
    root.after(100, lambda: update_simulators(root, simulators))
