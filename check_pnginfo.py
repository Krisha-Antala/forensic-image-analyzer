from PIL import Image
import os

path = r"c:\Users\KRISHA\Downloads\forenic image analyzer\Uploads\sunflower.png"

if os.path.exists(path):
    img = Image.open(path)
    print(f"Info keys: {img.info.keys()}")
    for k, v in img.info.items():
        if isinstance(v, (str, int, float)):
            print(f"{k}: {v}")
        else:
            print(f"{k}: [Binary Data...]")
else:
    print("File not found")
