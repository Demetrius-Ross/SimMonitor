from simulator import Simulator
from utils.simulator_map import get_simulator_name
from utils.image_loader import load_images
from utils.serial_handler import update_simulators, DEBUG_MODE
import tkinter as tk
import logging

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(message)s")
logger = logging.getLogger(__name__)

CONFIG = {
    "DEBUG_DELAY": 2000,
    "SERIAL_DELAY": 2000,
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
    return canvas, screenx / 7, screeny / 2

canvas, pixelratiox, pixelratioy = setup_canvas(root, CONFIG["BACKGROUND_COLOR"])
images = load_images()
logger.info("✅ Images Loaded")

simulators = {}

def add_simulator(device_id):
    if device_id not in simulators:
        simulator_name = get_simulator_name(device_id)
        col_index = len(simulators) % 7
        row_index = len(simulators) // 7

        x_pos = pixelratiox * col_index
        y_pos = pixelratioy * row_index

        simulators[device_id] = Simulator(device_id, simulator_name, x_pos, y_pos, canvas, images)
        logger.info(f"📌 New Simulator Added: {simulator_name} (ID: {device_id}) at Position ({col_index}, {row_index})")
        logger.info(f"📌 Total Simulators: {len(simulators)}")

def key_pressed(event):
    actions = {
        "escape": lambda: (logger.info("🔴 Exiting Fullscreen & Closing"), root.attributes("-fullscreen", False), root.destroy()),
        "f": lambda: (logger.info("🔲 Toggling Fullscreen"), root.attributes("-fullscreen", True))
    }
    action = actions.get(event.keysym.lower())
    if action:
        action()

root.bind("<KeyPress>", key_pressed)

# NOTE: We only call `update_simulators(...)` ONCE to avoid re-opening the same port.
update_simulators(root, simulators, add_simulator)

logger.info("🚀 Sim Monitor is now running...")

root.mainloop()
