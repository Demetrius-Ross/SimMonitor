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

simulators = {}
SCALE = 1.0  # default fallback

def reset_device(port):
    """Soft-reset the device using mpremote on the given port."""
    if not port:
        logger.warning("No chosen_port found. Possibly debug mode or no device discovered.")
        return
    logger.info(f"Soft-booting ESP32 on port {port}...")
    os.system(f"mpremote connect {port} reset")

def relaunch_gui_with_reset():
    """Restart the GUI with optional ESP32 reset"""
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    subprocess.Popen([python_exe, script_path, "--reset"])
    sys.exit(0)

def add_simulator(device_id):
    """Create simulator instance based on SIMULATOR_LAYOUT"""
    if device_id not in simulators:
        simulator_name = get_simulator_name(device_id)
        col_index, row_index = SIMULATOR_LAYOUT.get(device_id, (0, 0))

        # Apply scaling to layout spacing
        x_spacing = int(310 * SCALE)
        x_pos = int(10 * SCALE) + col_index * x_spacing
        if row_index == 1:
            y_pos = int(110 * SCALE) + row_index * int(450 * SCALE)
        else:
            y_pos = int(40 * SCALE) + row_index * int(450 * SCALE)

        simulators[device_id] = Simulator(device_id, simulator_name, x_pos, y_pos, canvas, images, SCALE)
        simulators[device_id].draw()

        logger.info(f"📌 New Simulator Added: {simulator_name} (ID: {device_id}) at Row={row_index},Col={col_index}")
        logger.info(f"📌 Total Simulators: {len(simulators)}")

def prepopulate_simulators():
    """Create all simulator slots in an offline state"""
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
    global root, canvas, SCALE

    # Handle optional reset flag
    do_reset = ("--reset" in sys.argv)
    if do_reset:
        fallback_port = "/dev/ttyUSB0"  # or "COM10" for Windows
        actual_port = chosen_port if chosen_port else fallback_port
        reset_device(actual_port)

    # Initialize GUI
    root = tk.Tk()
    root.title("Sim Monitor v1")
    root.attributes("-fullscreen", CONFIG["FULLSCREEN"])
    logger.info("✅ GUI Initialized (Fullscreen Mode: %s)", CONFIG["FULLSCREEN"])

    # Screen dimensions and scaling
    screenx = root.winfo_screenwidth()
    screeny = root.winfo_screenheight()
    BASE_WIDTH = 1280
    BASE_HEIGHT = 720
    SCALE_X = screenx / BASE_WIDTH
    SCALE_Y = screeny / BASE_HEIGHT
    SCALE = min(SCALE_X, SCALE_Y)

    canvas = tk.Canvas(root, width=screenx, height=screeny, bg=CONFIG["BACKGROUND_COLOR"])
    canvas.pack()
    logger.info(f"✅ Canvas Initialized: {screenx}x{screeny}, BG Color: {CONFIG['BACKGROUND_COLOR']}")

    # Load images
    global images
    images = load_images()
    logger.info("✅ Images Loaded")

    # Bind key events
    root.bind("<KeyPress>", key_pressed)

    # Populate simulators in offline state
    prepopulate_simulators()

    # Start serial monitor thread
    update_simulators(root, simulators, add_simulator)

    logger.info("🚀 Sim Monitor is now running...")
    root.mainloop()

if __name__ == "__main__":
    main()
