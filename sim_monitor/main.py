from simulator import Simulator
from utils.image_loader import load_images
from utils.serial_handler import update_simulators
import tkinter as tk

# Initialize Tkinter
root = tk.Tk()
root.title("Sim Monitor v1")
root.attributes("-fullscreen", True)

# Canvas for GUI
# canvas = tk.Canvas(root, width=1920, height=1080, bg="white")

#canvas.pack()

# Screen Resolution
screenx = root.winfo_screenwidth()
screeny = root.winfo_screenheight()
canvas = tk.Canvas(root, width=screenx, height=screeny, bg="white")
canvas.pack()
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
    key = event.keysym.lower()
    if key == "escape":
        root.attributes("-fullscreen", False)
        root.destroy()
    elif key == "f":
        root.attributes("-fullscreen", True)

root.bind("<KeyPress>", key_pressed)

# Different update intervals
DEBUG_DELAY = 2000  # Delay in milliseconds for debug mode
SERIAL_DELAY = 2000  # Delay in milliseconds for serial mode

# Start Simulator Updates
def update_simulators_wrapper():
    """
    Wrapper function to continuously update simulators using serial data.
    This function is non-blocking and uses Tkinter's `after` method.
    """
    from utils.serial_handler import DEBUG_MODE  # Import the debug flag from serial_handler

    update_simulators(root, simulators)
    delay = DEBUG_DELAY if DEBUG_MODE else SERIAL_DELAY  # Use different delays
    root.after(delay, update_simulators_wrapper)  # Schedule the next update

# Start the update loop
update_simulators_wrapper()

# Run the Main Loop
root.mainloop()
