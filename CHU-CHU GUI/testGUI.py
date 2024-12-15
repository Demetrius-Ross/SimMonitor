import tkinter as tk
from tkinter import PhotoImage
from PIL import Image, ImageTk
import random
import serial
import time

# Enable Debug Mode
DEBUG_MODE = True

# Serial Configuration
try:
    if not DEBUG_MODE:
        ser = serial.Serial('/dev/serial0', 115200, timeout=1)  # Adjust port if necessary
        print("Serial connection established")
    else:
        ser = None
except Exception as e:
    print(f"Serial connection error: {e}")
    ser = None

# Simulator Class
class Simulator:
    def __init__(self, name, x, y, canvas, images):
        self.name = name
        self.x = x
        self.y = y
        self.canvas = canvas
        self.images = images
        self.ramp_state = 0
        self.motion_state = 0
        self.status = 0
        self.elements = []

    def update_state(self, ramp_state, motion_state, status):
        self.ramp_state = ramp_state
        self.motion_state = motion_state
        self.status = status
        self.draw()

    def draw(self):
        # Clear previous drawings
        for element in self.elements:
            self.canvas.delete(element)
        self.elements.clear()

        # Determine images to display
        motion_image = self.images["motion_on"] if self.motion_state else self.images["motion_off"]
        ramp_image = self.images["ramp_up"] if self.ramp_state else self.images["ramp_down"]

        # Draw motion and ramp states
        self.elements.append(self.canvas.create_image(self.x + 40, self.y + 40, anchor="nw", image=motion_image))
        self.elements.append(self.canvas.create_image(self.x + 300, self.y + 40, anchor="nw", image=ramp_image))

        # Display text data
        self.elements.append(self.canvas.create_text(self.x + 60, self.y + 400, text=f"Motion: {'ON' if self.motion_state else 'OFF'}", font=("Helvetica", 14), fill="white"))
        self.elements.append(self.canvas.create_text(self.x + 60, self.y + 440, text=f"Ramp: {'Up' if self.ramp_state else 'Down'}", font=("Helvetica", 14), fill="white"))
        self.elements.append(self.canvas.create_text(self.x + 60, self.y + 480, text=f"Status: {'Connected' if self.status else 'No Data'}", font=("Helvetica", 14), fill="white"))

# Load Images
def load_images():
    image_paths = {
        "motion_on": "simup.jpg",   # Replace with actual image paths
        "motion_off": "simdown.jpg",
        "ramp_up": "rampup.jpg",
        "ramp_down": "rampdown.jpg"
    }

    images = {}
    for key, path in image_paths.items():
        try:
            img = Image.open(path).resize((240, 320))
            images[key] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Failed to load {path}: {e}")
            images[key] = None
    return images

# Update Simulators with Serial or Debug Data
def update_simulators():
    if DEBUG_MODE:
        # Generate random data for testing
        for sim in simulators:
            ramp_state = random.randint(0, 1)
            motion_state = random.randint(0, 1)
            status = random.randint(0, 1)
            sim.update_state(ramp_state, motion_state, status)
    else:
        if ser and ser.in_waiting > 0:
            try:
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
                print(f"Error processing serial data: {e}")

    # Schedule the next update
    root.after(1000, update_simulators)

# Key Bindings
def key_pressed(event):
    key = event.keysym.lower()
    if key == "escape":
        root.attributes("-fullscreen", False)
        root.destroy()
    elif key == "f":
        root.attributes("-fullscreen", True)

# Initialize Tkinter
root = tk.Tk()
root.title("Sim Monitor v1")
root.attributes("-fullscreen", True)

# Canvas
canvas = tk.Canvas(root, width=1920, height=1080, bg="green")
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

# Bind Keys
root.bind("<KeyPress>", key_pressed)

# Start Simulator Updates
update_simulators()

# Run the Main Loop
root.mainloop()
