import exifread
import os

path = r"c:\Users\KRISHA\Downloads\forenic image analyzer\Uploads\WhatsApp Image 2025-09-15 at 21.21.13_7e1141d7.jpg"

if os.path.exists(path):
    with open(path, "rb") as f:
        tags = exifread.process_file(f)
        print(f"Total tags found: {len(tags)}")
        for tag in tags.keys():
            if "Model" in tag or "DateTime" in tag or "Software" in tag or "GPS" in tag:
                print(f"{tag}: {tags[tag]}")
else:
    print("File not found")
