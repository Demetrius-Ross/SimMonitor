import os
import sys
import subprocess
import tkinter as tk
import logging
import time

from simulator import Simulator
from utils.simulator_map import get_simulator_name, SIMULATOR_LAYOUT
from utils.image_loader import load_images
from utils.serial_handler import update_simulators, chosen_port

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(message)s")

CONFIG = {
    "FULLSCREEN": True,
    "BACKGROUND_COLOR": "white"
}

def reset_device(port):
    """Soft-reset the device using mpremote on the given port."""
    if not port:
        logger.warning("No chosen_port found. Possibly debug mode or no device discovered.")
        return
    logger.info(f"Soft-booting ESP32 on port {port}...")
    os.system(f"mpremote connect {port} reset")

def relaunch_gui_with_reset():
    """
    1) Spawn a new instance of this script with --reset
    2) Kill the current instance
    """
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    subprocess.Popen([python_exe, script_path, "--reset"])
    sys.exit(0)

def add_simulator(device_id):
    """Dynamically create a simulator instance based on a fixed layout map."""
    if device_id not in simulators:
        simulator_name = get_simulator_name(device_id)

        # Look up (col, row) from SIMULATOR_LAYOUT
        col_index, row_index = SIMULATOR_LAYOUT.get(device_id, (0, 0))

        x_spacing = 310
        x_pos = 10 + col_index * x_spacing
        if row_index == 1:
            y_pos = 110 + row_index * 450
        else:
            y_pos = 40 + row_index * 450

        simulators[device_id] = Simulator(device_id, simulator_name, x_pos, y_pos, canvas, images)
        simulators[device_id].draw()

        logger.info(f"📌 New Simulator Added: {simulator_name} (ID: {device_id}) at Row={row_index},Col={col_index}")
        logger.info(f"📌 Total Simulators: {len(simulators)}")

def prepopulate_simulators():
    """Create all simulator slots from the known layout in an offline state."""
    for device_id in SIMULATOR_LAYOUT.keys():
        add_simulator(device_id)

def key_pressed(event):
    if event.keysym.lower() == "escape":
        logger.info("🔴 Exiting Fullscreen & Closing")
        root.attributes("-fullscreen", False)
        root.destroy()
        sys.exit(0)
    elif event.keysym.lower() == "f":
        logger.info("🔲 Toggling Fullscreen")
        root.attributes("-fullscreen", True)
    elif event.keysym.lower() == "r":
        logger.info("🔁 Restarting GUI with a soft ESP32 reset...")
        relaunch_gui_with_reset()

def main():
    # 1) Check if we have a --reset argument
    do_reset = ("--reset" in sys.argv)

    # 2) If the user requested a reset, do it before opening the port
    if do_reset:
        # We might not have a chosen_port yet, fallback if needed
        fallback_port = "/dev/ttyUSB0"  # or "COM10" on Windows
        actual_port = chosen_port if chosen_port else fallback_port
        reset_device(actual_port)

    # 3) Now proceed with normal GUI setup
    global root, canvas, simulators
    root = tk.Tk()
    root.title("Sim Monitor v1")
    root.attributes("-fullscreen", CONFIG["FULLSCREEN"])
    logger.info("✅ GUI Initialized (Fullscreen Mode: %s)", CONFIG["FULLSCREEN"])

    # Create canvas
    screenx = root.winfo_screenwidth()
    screeny = root.winfo_screenheight()
    canvas = tk.Canvas(root, width=screenx, height=screeny, bg=CONFIG["BACKGROUND_COLOR"])
    canvas.pack()
    logger.info(f"✅ Canvas Initialized: {screenx}x{screeny}, BG Color: {CONFIG['BACKGROUND_COLOR']}")

    # Load images
    from utils.image_loader import load_images
    global images
    images = load_images()
    logger.info("✅ Images Loaded")

    # Create simulators dict
    simulators.clear()

    # Bind keys
    root.bind("<KeyPress>", key_pressed)

    # Pre-populate all simulators
    prepopulate_simulators()

    # Start the serial handler in a separate thread
    from utils.serial_handler import update_simulators
    update_simulators(root, simulators, add_simulator)

    logger.info("🚀 Sim Monitor is now running...")
    root.mainloop()

if __name__ == "__main__":
    main()
