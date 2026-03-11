# Forensic Image Analyzer

The **Forensic Image Analyzer** is a simple web application that analyzes images to discover hidden information. It can extract metadata, detect hidden messages using steganography, and generate a digital fingerprint of the image.

This project demonstrates basic techniques used in **digital forensics and cybersecurity investigations**.

---

## Features

* Upload and analyze image files
* Extract basic image metadata
* Detect hidden messages embedded using LSB steganography
* Generate an MD5 hash (digital fingerprint) of the image
* Display image details such as format, color mode, and resolution

---

## Technologies Used

This project was built using:

* Python
* Flask
* Pillow (PIL) – image processing
* ExifRead – metadata extraction
* Stegano – steganography detection
* HTML and CSS – front-end interface

---

## Project Structure

```id="x0jqfy"
forensic-image-analyzer
│
├── app.py
├── requirements.txt
│
├── uploads
│
├── static
│
└── templates
    └── index.html
```

---

## How to Run the Project

### 1. Clone the repository

```id="m7p7xg"
git clone https://github.com/yourusername/forensic-image-analyzer.git
cd forensic-image-analyzer
```

### 2. Install dependencies

```id="wnpf9o"
pip install -r requirements.txt
```

### 3. Start the application

```id="g2d9cr"
python app.py
```

### 4. Open the website

---

## How the Analyzer Works

When an image is uploaded, the application performs several checks.

### Metadata Extraction

The tool looks for EXIF metadata such as camera details, GPS information, and timestamps.

### Digital Fingerprint

An **MD5 hash** is generated for the uploaded file. This helps verify whether the image has been modified.

### Steganography Detection

The application checks for hidden messages embedded in the image using **LSB (Least Significant Bit) steganography**.

### Image Information

Basic properties like format, color mode, and resolution are extracted from the image.

---

## Testing the Tool

You can test the analyzer with:

* Normal photos
* Camera images containing metadata
* Images with hidden messages

Example of embedding a hidden message:

```python
from stegano import lsb

secret = lsb.hide("image.png", "Hidden message")
secret.save("hidden_image.png")
```

Upload the generated image to the analyzer to detect the hidden message.

---

## Future Improvements

Possible improvements that could be added later:

* Error Level Analysis (ELA) for detecting image manipulation
* SHA256 hashing
* Steganography heatmap visualization
* Deepfake detection

---

## License

This project is open-source and available under the MIT License.

---

## Author

Krisha
Cybersecurity / Digital Forensics Project
