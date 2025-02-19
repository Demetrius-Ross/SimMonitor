from simulator import Simulator
from utils.simulator_map import get_simulator_name
from utils.image_loader import load_images
from utils.serial_handler import update_simulators, DEBUG_MODE
import tkinter as tk
import logging

# === Logging Configuration ===
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# === Configuration ===
CONFIG = {
    "DEBUG_DELAY": 2000,  # Delay in milliseconds for debug mode
    "SERIAL_DELAY": 2000,  # Delay in milliseconds for serial mode
    "FULLSCREEN": True,
    "BACKGROUND_COLOR": "white"
}

logger.info("🔧 Initializing Sim Monitor...")

# === Initialize Tkinter ===
root = tk.Tk()
root.title("Sim Monitor v1")
root.attributes("-fullscreen", CONFIG["FULLSCREEN"])
logger.info("✅ GUI Initialized (Fullscreen Mode: %s)", CONFIG["FULLSCREEN"])

# === Canvas Setup ===
def setup_canvas(root, bg_color):
    screenx = root.winfo_screenwidth()
    screeny = root.winfo_screenheight()
    canvas = tk.Canvas(root, width=screenx, height=screeny, bg=bg_color)
    canvas.pack()
    logger.info(f"✅ Canvas Initialized: {screenx}x{screeny}, BG Color: {bg_color}")
    return canvas, screenx / 7, screeny / 2  # 7 columns, 2 rows

canvas, pixelratiox, pixelratioy = setup_canvas(root, CONFIG["BACKGROUND_COLOR"])

# === Load Images ===
images = load_images()
logger.info("✅ Images Loaded")

# === Store Simulators (Mapped by Device ID) ===
simulators = {}

# === Function to Create a Simulator for a New Device ID ===
def add_simulator(device_id):
    """Dynamically create a simulator instance if an unknown device ID appears."""
    if device_id not in simulators:
        simulator_name = get_simulator_name(device_id)  # Get name from ID
        
        col_index = len(simulators) % 7  # 7 per row
        row_index = len(simulators) // 7  # Stack new row after 7

        x_pos = pixelratiox * col_index
        y_pos = pixelratioy * row_index

        # ✅ Pass `device_id` to the `Simulator`
        simulators[device_id] = Simulator(device_id, simulator_name, x_pos, y_pos, canvas, images)
        
        # ✅ Debugging Log
        logger.info(f"📌 New Simulator Added: {simulator_name} (ID: {device_id}) at Position ({col_index}, {row_index})")
        logger.info(f"📌 Total Simulators: {len(simulators)}")


# === Key Bindings ===
def key_pressed(event):
    actions = {
        "escape": lambda: (logger.info("🔴 Exiting Fullscreen & Closing"), root.attributes("-fullscreen", False), root.destroy()),
        "f": lambda: (logger.info("🔲 Toggling Fullscreen"), root.attributes("-fullscreen", True))
    }
    action = actions.get(event.keysym.lower())
    if action:
        action()

root.bind("<KeyPress>", key_pressed)

# === Update Simulators Based on Serial Data ===
def update_simulators_wrapper():
    try:
        update_simulators(root, simulators, add_simulator)  # ✅ Ensures add_simulator is passed
        delay = CONFIG["DEBUG_DELAY"] if DEBUG_MODE else CONFIG["SERIAL_DELAY"]
        root.after(delay, update_simulators_wrapper)
    except Exception as e:
        logger.error(f"❌ Error in simulator update: {e}")

# === Start the Update Loop ===
update_simulators_wrapper()

logger.info("🚀 Sim Monitor is now running...")

# === Run the Main Loop ===
root.mainloop()
