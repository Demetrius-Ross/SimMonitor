from simulator import Simulator
from utils.image_loader import load_images
from utils.serial_handler import update_simulators, DEBUG_MODE
import tkinter as tk

# Configuration
CONFIG = {
    "DEBUG_DELAY": 2000,  # Delay in milliseconds for debug mode
    "SERIAL_DELAY": 2000,  # Delay in milliseconds for serial mode
    "FULLSCREEN": True,
    "BACKGROUND_COLOR": "white"
}

# Initialize Tkinter
root = tk.Tk()
root.title("Sim Monitor v1")
root.attributes("-fullscreen", CONFIG["FULLSCREEN"])

# Canvas Setup
def setup_canvas(root, bg_color):
    screenx = root.winfo_screenwidth()
    screeny = root.winfo_screenheight()
    canvas = tk.Canvas(root, width=screenx, height=screeny, bg=bg_color)
    canvas.pack()
    return canvas, screenx / 6, screeny / 2

canvas, pixelratiox, pixelratioy = setup_canvas(root, CONFIG["BACKGROUND_COLOR"])

# Load Images
images = load_images()

# Create Simulators
simulator_names = ["PC-12", "ERJ-24", "EC-135"]
simulators = [
    Simulator(name, pixelratiox * idx, pixelratioy * 0, canvas, images)
    for idx, name in enumerate(simulator_names)
]

# Key Bindings
def key_pressed(event):
    actions = {
        "escape": lambda: (root.attributes("-fullscreen", False), root.destroy()),
        "f": lambda: root.attributes("-fullscreen", True)
    }
    action = actions.get(event.keysym.lower())
    if action:
        action()

root.bind("<KeyPress>", key_pressed)

# Update Simulators
def update_simulators_wrapper():
    try:
        update_simulators(root, simulators)
        delay = CONFIG["DEBUG_DELAY"] if DEBUG_MODE else CONFIG["SERIAL_DELAY"]
        root.after(delay, update_simulators_wrapper)
    except Exception as e:
        print(f"Error in simulator update: {e}")

# Start the update loop
update_simulators_wrapper()

# Run the Main Loop
root.mainloop()
