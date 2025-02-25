from simulator import Simulator
from utils.simulator_map import get_simulator_name, SIMULATOR_LAYOUT
from utils.image_loader import load_images
from utils.serial_handler import update_simulators, DEBUG_MODE
import tkinter as tk
import logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)

CONFIG = {
    "FULLSCREEN": True,
    "BACKGROUND_COLOR": "white"
}

logger.info("🔧 Initializing Sim Monitor...")

root = tk.Tk()
root.title("Sim Monitor v1")
root.attributes("-fullscreen", CONFIG["FULLSCREEN"])
logger.info("✅ GUI Initialized (Fullscreen Mode: %s)", CONFIG["FULLSCREEN"])

def setup_canvas(root, bg_color):
    screenx = root.winfo_screenwidth()
    screeny = root.winfo_screenheight()
    canvas = tk.Canvas(root, width=screenx, height=screeny, bg=bg_color)
    canvas.pack()
    logger.info(f"✅ Canvas Initialized: {screenx}x{screeny}, BG Color: {bg_color}")
    return canvas

canvas = setup_canvas(root, CONFIG["BACKGROUND_COLOR"])
images = load_images()
logger.info("✅ Images Loaded")

simulators = {}

def add_simulator(device_id):
    """Dynamically create a simulator instance based on a fixed layout map."""
    if device_id not in simulators:
        simulator_name = get_simulator_name(device_id)

        # Look up (col, row) from SIMULATOR_LAYOUT
        if device_id in SIMULATOR_LAYOUT:
            col_index, row_index = SIMULATOR_LAYOUT[device_id]
        else:
            # If device_id not in layout, default to (0,0) or skip
            col_index, row_index = (0, 0)
        x_spacing = 310
        # Now compute x,y from col,row
        # e.g. each col is 400 px wide, each row is 450 px tall
        x_pos = 10 + col_index * x_spacing
        if row_index==1:
            y_pos = 110 + row_index * 450
        else:
            y_pos = 40 + row_index * 450

        # Create the simulator
        simulators[device_id] = Simulator(device_id, simulator_name, x_pos, y_pos, canvas, images)

        simulators[device_id].draw()

        logger.info(f"📌 New Simulator Added: {simulator_name} (ID: {device_id}) at Row={row_index},Col={col_index}")
        logger.info(f"📌 Total Simulators: {len(simulators)}")

def key_pressed(event):
    if event.keysym.lower() == "escape":
        logger.info("🔴 Exiting Fullscreen & Closing")
        root.attributes("-fullscreen", False)
        root.destroy()
    elif event.keysym.lower() == "f":
        logger.info("🔲 Toggling Fullscreen")
        root.attributes("-fullscreen", True)

root.bind("<KeyPress>", key_pressed)

def prepopulate_simulators():
    for device_id in SIMULATOR_LAYOUT.keys():
        add_simulator(device_id)


prepopulate_simulators()

# *** Call update_simulators once ***
update_simulators(root, simulators, add_simulator)

logger.info("🚀 Sim Monitor is now running...")

root.mainloop()
