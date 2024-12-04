from PIL import Image, ImageTk

def load_images():
    image_paths = {
        "motion_on": "assets/simup.jpg",
        "motion_off": "assets/simdown.jpg"
    }

    images = {}
    for key, path in image_paths.items():
        try:
            img = Image.open(path).resize((240, 240))  # 1:1 aspect ratio
            images[key] = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Failed to load {path}: {e}")
            images[key] = None
    return images
