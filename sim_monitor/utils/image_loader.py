from PIL import Image, ImageTk
import os

def load_images():
    # Get absolute path to directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Go up one level and into the assets directory
    asset_dir = os.path.join(script_dir, "..", "assets")

    image_paths = {
        "motion_up": os.path.join(asset_dir, "simup.jpg"),
        "motion_down": os.path.join(asset_dir, "simdown.jpg")
    }

    images = {}
    for key, path in image_paths.items():
        try:
            img = Image.open(path).resize((320, 320))  # 1:1 aspect ratio
            images[key] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"❌ Failed to load {path}: {e}")
            images[key] = None
    return images
