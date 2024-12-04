import tkinter as tk
from simulator import Simulator
from utils.image_loader import load_images
from utils.serial_handler import update_simulators

# Initialize Tkinter
root = tk.Tk()
root.title("Sim Monitor v1")
root.attributes("-fullscreen", True)

# Canvas for GUI
canvas = tk.Canvas(root, width=1920, height=1080, bg="white")
canvas.pack()

# Screen Resolution
screenx = root.winfo_screenwidth()
screeny = root.winfo_screenheight()
pixelratiox = screenx / 6
pixelratioy = screeny / 2

# Load Images
images = load_images()

# Create Simulators
simulators = [
    Simulator("PC-12", pixelratiox * 0, pixelratioy * 0, canvas, images)
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

# Start Simulator Updates
update_simulators(root, simulators)

# Run the Main Loop
root.mainloop()
