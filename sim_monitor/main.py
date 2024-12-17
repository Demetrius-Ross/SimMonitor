from simulator import Simulator
from utils.image_loader import load_images
from utils.serial_handler import update_simulators, DEBUG_MODE
import tkinter as tk

# Initialize Tkinter
root = tk.Tk()
root.title("Sim Monitor v1")
root.attributes("-fullscreen", True)

# Screen Resolution
screenx = root.winfo_screenwidth()
screeny = root.winfo_screenheight()
canvas = tk.Canvas(root, width=screenx, height=screeny, bg="white")
canvas.pack()

# Pixel ratios
pixelratiox = screenx / 6
pixelratioy = screeny / 2

# Load Images
images = load_images()

# Create Simulators
simulators = [
    Simulator("PC-12", pixelratiox * 0, pixelratioy * 0, canvas, images),
    Simulator("ERJ-24", pixelratiox * 1, pixelratioy * 0, canvas, images),
    Simulator("EC-130", pixelratiox * 2, pixelratioy * 0, canvas, images)
]

# Key Bindings
def key_pressed(event):
    """Handle key events for fullscreen toggle and exiting."""
    key = event.keysym.lower()
    if key == "escape":  # Exit full-screen or close
        root.destroy()
    elif key == "f":  # Toggle full-screen
        root.attributes("-fullscreen", not root.attributes("-fullscreen"))

root.bind("<KeyPress>", key_pressed)

# Update Intervals
DEBUG_DELAY = 2000  # Delay in milliseconds for debug mode
SERIAL_DELAY = 200  # Delay in milliseconds for serial mode (lowered for real-time updates)

# Determine delay based on DEBUG_MODE
update_delay = DEBUG_DELAY if DEBUG_MODE else SERIAL_DELAY

# Start Simulator Updates
def update_simulators_wrapper():
    """
    Continuously update simulators using serial data in a non-blocking way.
    """
    try:
        update_simulators(root, simulators)
    except Exception as e:
        print(f"Error during simulator update: {e}")  # Safeguard against errors

    root.after(update_delay, update_simulators_wrapper)  # Schedule the next update

# Start the update loop
update_simulators_wrapper()

# Run the Main Loop
try:
    root.mainloop()
except KeyboardInterrupt:
    print("Program exited cleanly.")
