from PIL import Image, ImageTk
import os

def load_images(scale=1.0):
    # Get absolute path to this script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Resolve path to assets directory
    asset_dir = os.path.join(script_dir, "..", "assets")

    # Image paths
    image_paths = {
        "motion_up": os.path.join(asset_dir, "simup.jpg"),
        "motion_down": os.path.join(asset_dir, "simdown.jpg")
    }

    # Apply scaling to image dimensions
    base_size = 320  # original size
    scaled_size = int(base_size * scale)

    images = {}
    for key, path in image_paths.items():
        try:
            img = Image.open(path).resize((scaled_size, scaled_size))
            images[key] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"❌ Failed to load {path}: {e}")
            images[key] = None

    return images
