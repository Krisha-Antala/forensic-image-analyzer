import os
import hashlib
import re
import json
import base64
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, abort
from PIL import Image, ImageChops, ImageEnhance
import exifread
import sys
from unittest.mock import MagicMock

# --- Headless Environment Fix ---
try:
    import cv2
except ImportError:
    print("Warning: OpenCV import failed. Using mock for headless environment.")
    sys.modules["cv2"] = MagicMock()
    import cv2

from stegano import lsb
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Vercel fix for Matplotlib config directory
os.environ['MPLCONFIGDIR'] = "/tmp"

app = Flask(__name__)

# ─── Analysis Helpers ────────────────────────────────────────────────────────

def perform_ela(image_bytes, quality=90):
    try:
        original = Image.open(BytesIO(image_bytes)).convert('RGB')
        
        # In-memory ELA processing
        temp_io = BytesIO()
        original.save(temp_io, 'JPEG', quality=quality)
        temp_io.seek(0)
        temporary = Image.open(temp_io)
        
        ela_image = ImageChops.difference(original, temporary)
        extrema = ela_image.getextrema()
        max_diff = max([ex[1] for ex in extrema])
        scale = 255.0 / (max_diff if max_diff > 0 else 1)
        ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
        
        buffered = BytesIO()
        ela_image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"ELA Error: {e}")
        return None


def get_histogram(image_bytes):
    try:
        # Check if cv2 is actually functional
        if isinstance(cv2, MagicMock):
            print("Histogram skipped: OpenCV is not available.")
            return None

        # Convert bytes to numpy array for OpenCV
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None or isinstance(img, MagicMock):
            return None

        BG_COLOR   = "#0d1117"
        CARD_COLOR = "#161b22"
        GRID_COLOR = "#30363d"
        TEXT_COLOR = "#e6edf3"
        CH_COLORS  = {"Blue": "#38bdf8", "Green": "#4ade80", "Red": "#f87171"}

        fig, axes = plt.subplots(1, 3, figsize=(14, 4), dpi=120)
        fig.patch.set_facecolor(BG_COLOR)
        fig.suptitle("RGB Channel Histogram", color=TEXT_COLOR,
                     fontsize=14, fontweight="bold", y=1.02, fontfamily="monospace")

        for ax, (name, idx) in zip(axes, [("Blue", 0), ("Green", 1), ("Red", 2)]):
            hist  = cv2.calcHist([img], [idx], None, [256], [0, 256]).flatten()
            x     = np.arange(256)
            color = CH_COLORS[name]
            ax.fill_between(x, hist, alpha=0.25, color=color)
            ax.plot(x, hist, color=color, linewidth=2.0)
            ax.set_facecolor(CARD_COLOR)
            ax.set_xlim(0, 255)
            ax.set_ylim(0)
            ax.set_xlabel("Pixel Intensity (0–255)", color=TEXT_COLOR, fontsize=9, fontfamily="monospace")
            ax.set_ylabel("Pixel Count", color=TEXT_COLOR, fontsize=9, fontfamily="monospace")
            ax.set_title(f"{name} Channel", color=color, fontsize=11,
                         fontweight="bold", fontfamily="monospace", pad=8)
            ax.tick_params(colors=TEXT_COLOR, labelsize=8)
            ax.yaxis.set_major_formatter(
                ticker.FuncFormatter(lambda v, _: f"{int(v/1000)}k" if v >= 1000 else str(int(v)))
            )
            for spine in ax.spines.values():
                spine.set_edgecolor(GRID_COLOR)
            ax.grid(True, color=GRID_COLOR, linewidth=0.6, linestyle="--", alpha=0.7)
            peak_x = int(np.argmax(hist))
            peak_y = hist[peak_x]
            ax.annotate(f"Peak: {peak_x}", xy=(peak_x, peak_y),
                        xytext=(peak_x + 15, peak_y * 0.85),
                        color=color, fontsize=8, fontfamily="monospace",
                        arrowprops=dict(arrowstyle="->", color=color, lw=1.0), clip_on=True)

        plt.tight_layout(rect=[0, 0, 1, 1])
        
        buffered = BytesIO()
        plt.savefig(buffered, format="PNG", facecolor=BG_COLOR, bbox_inches="tight", pad_inches=0.3)
        plt.close(fig)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Histogram Error: {e}")
        return None


def extract_strings(data, min_len=6):
    try:
        pattern = bytes(f"[ -~]{{{min_len},}}", 'ascii')
        matches = re.findall(pattern, data)
        return [m.decode('ascii') for m in matches[:60]]
    except Exception:
        return []


def generate_pdf_report(report_data, original_image_bytes):
    from fpdf import FPDF

    def clean(s):
        return str(s).replace('×', 'x').replace('—', '-').encode('latin-1', errors='replace').decode('latin-1')

    class ForensicPDF(FPDF):
        def header(self):
            self.set_fill_color(13, 17, 23)
            self.rect(0, 0, 210, 30, 'F')
            self.set_text_color(56, 189, 248)
            self.set_font("Helvetica", "B", 16)
            self.set_y(8)
            self.cell(0, 10, clean("FORENSIC IMAGE ANALYSIS REPORT"), align="C")
            self.set_text_color(150, 150, 170)
            self.set_font("Helvetica", "", 8)
            self.set_y(20)
            self.cell(0, 6, clean(f"Generated: {report_data.get('timestamp', '')}   |   File: {report_data.get('filename', '')}"), align="C")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_fill_color(13, 17, 23)
            self.rect(0, 282, 210, 15, 'F')
            self.set_text_color(100, 100, 120)
            self.set_font("Helvetica", "I", 8)
            self.cell(0, 10, clean(f"Forensic Image Analyzer  |  Page {self.page_no()}"), align="C")

        def section_title(self, title, icon=""):
            self.ln(4)
            self.set_fill_color(22, 27, 34)
            self.set_draw_color(56, 189, 248)
            self.set_line_width(0.5)
            self.set_text_color(56, 189, 248)
            self.set_font("Helvetica", "B", 11)
            self.set_fill_color(22, 27, 34)
            self.cell(0, 10, clean(f"  {icon}  {title}"), border="L", fill=True, ln=True)
            self.set_line_width(0.2)
            self.ln(2)

        def kv_row(self, key, value, alt=False):
            if alt:
                self.set_fill_color(25, 32, 42)
            else:
                self.set_fill_color(18, 24, 32)
            self.set_text_color(140, 160, 180)
            self.set_font("Helvetica", "", 9)
            self.cell(60, 7, clean(f"  {key}"), fill=True)
            self.set_text_color(220, 230, 243)
            self.set_font("Courier", "", 8.5)
            val_str = str(value)
            if len(val_str) > 75:
                val_str = val_str[:72] + "..."
            self.cell(0, 7, clean(f"  {val_str}"), fill=True, ln=True)

        def alert_box(self, text, color_r=56, color_g=189, color_b=248):
            self.set_fill_color(color_r // 6, color_g // 6, color_b // 6)
            self.set_draw_color(color_r, color_g, color_b)
            self.set_line_width(0.3)
            self.set_text_color(color_r, color_g, color_b)
            self.set_font("Courier", "B", 9.5)
            self.cell(0, 10, clean(f"  {text}"), border=1, fill=True, ln=True)
            self.set_line_width(0.2)

    pdf = ForensicPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(15, 35, 15)
    pdf.add_page()
    pdf.set_fill_color(13, 17, 23)

    # ── Thumbnail ──────────────────────────────────────────────────────────
    if original_image_bytes:
        try:
            from PIL import Image as PILImage
            thumb_io = BytesIO()
            im = PILImage.open(BytesIO(original_image_bytes)).convert("RGB")
            im.thumbnail((160, 160))
            im.save(thumb_io, "JPEG")
            pdf.image(thumb_io, x=15, y=38, w=55)

            # ELA thumbnail
            ela_base64 = report_data.get("ela_base64")
            if ela_base64:
                ela_thumb_io = BytesIO()
                ela_im = PILImage.open(BytesIO(base64.b64decode(ela_base64))).convert("RGB")
                ela_im.thumbnail((160, 160))
                ela_im.save(ela_thumb_io, "JPEG")
                pdf.image(ela_thumb_io, x=80, y=38, w=55)
                pdf.set_y(38 + 40)
                pdf.set_x(80)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(100, 150, 200)
                pdf.cell(55, 5, clean("ELA Compression Map"), align="C", ln=True)

            pdf.set_y(100)
        except Exception as e:
            print(f"Thumbnail Error: {e}")
            pdf.set_y(40)

    # ── Image Properties ──────────────────────────────────────────────────
    pdf.section_title("IMAGE PROPERTIES", "[INFO]")
    info = report_data.get("image_info", {})
    for i, (k, v) in enumerate(info.items()):
        pdf.kv_row(k, v, alt=(i % 2 == 1))

    # ── Forensic Identifiers ─────────────────────────────────────────────
    pdf.section_title("FORENSIC IDENTIFIERS", "[EXIF]")
    fd = report_data.get("forensic_details", {})
    if fd:
        for i, (k, v) in enumerate(fd.items()):
            pdf.kv_row(k, v, alt=(i % 2 == 1))
    else:
        pdf.set_text_color(180, 100, 100)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 7, clean("  No EXIF forensic markers found"), ln=True)

    # ── Hash Fingerprints ────────────────────────────────────────────────
    pdf.section_title("DATA INTEGRITY FINGERPRINTS", "[HASH]")
    for i, (k, v) in enumerate(report_data.get("hashes", {}).items()):
        pdf.kv_row(k, v, alt=(i % 2 == 1))

    # ── Steganography ────────────────────────────────────────────────────
    pdf.section_title("STEGANOGRAPHIC SCAN RESULT", "[LSB]")
    steg = report_data.get("hidden_message", "No scan performed.")
    pdf.alert_box(steg, color_r=16, color_g=185, color_b=129)

    # ── Histogram ────────────────────────────────────────────────────────
    hist_base64 = report_data.get("hist_base64")
    if hist_base64:
        try:
            pdf.section_title("SPECTRAL DISTRIBUTION (HISTOGRAM)", "[CHART]")
            hist_io = BytesIO(base64.b64decode(hist_base64))
            pdf.image(hist_io, x=15, w=180)
            pdf.ln(4)
        except Exception:
            pass

    # ── Full Metadata ────────────────────────────────────────────────────
    meta = report_data.get("metadata", {})
    if meta:
        pdf.section_title(f"FULL EXIF METADATA DUMP ({len(meta)} items)", "[DATA]")
        for i, (k, v) in enumerate(sorted(meta.items())):
            pdf.kv_row(k, v, alt=(i % 2 == 1))

    # ── Strings ──────────────────────────────────────────────────────────
    strs = report_data.get("strings", [])
    if strs:
        pdf.section_title(f"EMBEDDED ASCII STRINGS ({len(strs)} found)", "[STR]")
        pdf.set_font("Courier", "", 8)
        pdf.set_text_color(165, 243, 252)
        for s in strs:
            if pdf.get_y() > 260:
                pdf.add_page()
            s_clean = clean(s)
            if len(s_clean) > 95:
                s_clean = s_clean[:92] + "..."
            pdf.set_fill_color(10, 20, 30)
            pdf.cell(0, 5, clean(f"  {s_clean}"), fill=True, ln=True)

    return pdf.output()


# ─── Routes ─────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    hidden_message   = None
    metadata         = {}
    forensic_details = {}
    image_info       = None
    hashes           = {}
    strings          = []
    filename         = None
    ela_url          = None
    hist_url         = None
    pdf_base64       = None
    error            = None
    original_base64  = None

    if request.method == "POST":
        file = request.files.get("image")
        if file and file.filename != "":
            filename = file.filename
            image_bytes = file.read()
            
            # Validate image
            try:
                img = Image.open(BytesIO(image_bytes))
                img.verify()
                img = Image.open(BytesIO(image_bytes))
                
                # Store original (or resized) base64 for display
                # To avoid Vercel 4.5MB payload limit, we resize the preview if too large
                if len(image_bytes) > 2 * 1024 * 1024: # > 2MB
                    preview_img = img.copy()
                    preview_img.thumbnail((1200, 1200))
                    prev_io = BytesIO()
                    preview_img.save(prev_io, format="JPEG", quality=85)
                    original_base64 = base64.b64encode(prev_io.getvalue()).decode('utf-8')
                else:
                    original_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    
            except Exception as e:
                print(f"Validation error: {e}")
                error = "The uploaded file is not a valid image. Please upload a JPG, PNG, WEBP, BMP, or GIF."
                return render_template("index.html", error=error)

            image_info = {
                "Format":   img.format,
                "Mode":     img.mode,
                "Size":     f"{img.size[0]} x {img.size[1]} px",
                "Filename": filename,
            }

            forensic_mapping = {
                "Model":            "Camera Model",
                "DateTimeOriginal": "Date Taken",
                "Software":         "Software",
                "Make":             "Make / Manufacturer",
                "GPS":              "GPS Coordinates",
            }

            try:
                if hasattr(img, 'text'):
                    for k, v in img.text.items():
                        metadata[f"PNG: {k}"] = str(v)
                exif_data = img.getexif()
                if exif_data:
                    from PIL.ExifTags import TAGS
                    for tid, val in exif_data.items():
                        tname = TAGS.get(tid, tid)
                        if isinstance(val, (str, int, float)):
                            metadata[f"Exif: {tname}"] = str(val)
                            for p, l in forensic_mapping.items():
                                if p.lower() in str(tname).lower():
                                    forensic_details[l] = str(val)
                
                # ExifRead from bytes
                tags = exifread.process_file(BytesIO(image_bytes), details=False)
                for k, v in tags.items():
                    metadata[k] = str(v)
                    for p, l in forensic_mapping.items():
                        if p in k:
                            forensic_details[l] = str(v)
            except Exception:
                pass

            ela_base64 = perform_ela(image_bytes)
            if ela_base64:
                ela_url = f"data:image/png;base64,{ela_base64}"

            hist_base64 = get_histogram(image_bytes)
            if hist_base64:
                hist_url = f"data:image/png;base64,{hist_base64}"

            try:
                if img.format in ['PNG', 'BMP']:
                    # Stegano works with file paths or BytesIO
                    msg = lsb.reveal(BytesIO(image_bytes))
                    hidden_message = msg if msg else "No LSB hidden message found."
                else:
                    hidden_message = f"LSB scan skipped for {img.format} format."
            except Exception:
                hidden_message = "No hidden message found."

            try:
                hashes["MD5"]     = hashlib.md5(image_bytes).hexdigest()
                hashes["SHA-256"] = hashlib.sha256(image_bytes).hexdigest()
                hashes["SHA-1"]   = hashlib.sha1(image_bytes).hexdigest()
                strings = extract_strings(image_bytes)
            except Exception:
                hashes["Error"] = "Hash calculation failed"

            # ── PDF Report ─────────────────────
            report_data = {
                "filename":        filename,
                "timestamp":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image_info":      image_info,
                "forensic_details": forensic_details,
                "hashes":          hashes,
                "hidden_message":  hidden_message,
                "metadata":        metadata,
                "strings":         strings,
                "ela_base64":      ela_base64,
                "hist_base64":     hist_base64,
            }
            
            try:
                pdf_bytes = generate_pdf_report(report_data, image_bytes)
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            except Exception as e:
                print(f"PDF Error: {e}")

    return render_template("index.html",
                           hidden_message=hidden_message,
                           metadata=metadata,
                           forensic_details=forensic_details,
                           image_info=image_info,
                           hashes=hashes,
                           strings=strings,
                           ela_url=ela_url,
                           hist_url=hist_url,
                           error=error,
                           original_url=f"data:image/png;base64,{original_base64}" if original_base64 else None,
                           pdf_base64=pdf_base64)


if __name__ == '__main__':
    app.run(debug=True)
