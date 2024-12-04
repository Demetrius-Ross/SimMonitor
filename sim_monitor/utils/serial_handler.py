import random
import serial

DEBUG_MODE = True

def update_simulators(root, simulators):
    if DEBUG_MODE:
        # Generate random data for testing
        for sim in simulators:
            ramp_state = random.randint(0, 1)
            motion_state = random.randint(0, 1)
            status = random.randint(0, 1)
            sim.update_state(ramp_state, motion_state, status)
    else:
        try:
            ser = serial.Serial('/dev/ttyUDB0', 115200, timeout=1)
            if ser.in_waiting > 0:
                data = ser.readline().decode("utf-8").strip()
                parts = data.split(",")  # Format: "sim_name,ramp_state,motion_state,status"
                if len(parts) == 4:
                    sim_name, ramp_state, motion_state, status = parts
                    ramp_state = int(ramp_state)
                    motion_state = int(motion_state)
                    status = int(status)

                    for sim in simulators:
                        if sim.name == sim_name:
                            sim.update_state(ramp_state, motion_state, status)
                            break
        except Exception as e:
            print(f"Serial communication error: {e}")

    # Schedule the next update
    root.after(1000, lambda: update_simulators(root, simulators))
