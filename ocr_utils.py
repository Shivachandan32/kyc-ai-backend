import pytesseract
import cv2
import numpy as np
import re
import io
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ExifTags
import os
import gc
from concurrent.futures import ThreadPoolExecutor, as_completed
import time  # optional


# ------------------------------------------------------------
# ✅ Configure Tesseract
# ------------------------------------------------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\patel\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
os.environ["TESSDATA_PREFIX"] = r"C:\Users\patel\AppData\Local\Programs\Tesseract-OCR\tessdata"
os.environ["OMP_THREAD_LIMIT"] = "1"


# ------------------------------------------------------------
# 🧠 IMAGE ORIENTATION FIX
# ------------------------------------------------------------
def fix_image_orientation(image: Image.Image) -> Image.Image:
    """Fix image orientation based on EXIF data."""
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = image._getexif()
        if exif is not None:
            orientation_value = exif.get(orientation)
            if orientation_value == 3:
                image = image.rotate(180, expand=True)
            elif orientation_value == 6:
                image = image.rotate(270, expand=True)
            elif orientation_value == 8:
                image = image.rotate(90, expand=True)
    except Exception:
        pass
    return image


# ------------------------------------------------------------
# 🧩 IMAGE PREPROCESSING (Optimized for OCR)
# ------------------------------------------------------------
def preprocess_pan_image(image: Image.Image) -> Image.Image:
    """Enhance image for OCR accuracy (optimized)."""
    image = fix_image_orientation(image)
    image = image.convert('RGB')

    cv_img = np.array(image)
    cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)

    # 🔧 Step 1: Denoise and normalize
    cv_img = cv2.bilateralFilter(cv_img, 9, 75, 75)

    # 🔧 Step 2: Reduce blue tint (for PAN cards)
    b, g, r = cv2.split(cv_img)
    cv_img = cv2.merge((
        np.clip(b * 0.8, 0, 255).astype(np.uint8),
        np.clip(g * 1.1, 0, 255).astype(np.uint8),
        np.clip(r * 1.2, 0, 255).astype(np.uint8)
    ))

    # 🔧 Step 3: Grayscale + Histogram Equalization
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    # 🔧 Step 4: Adaptive Thresholding for better contrast
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 2
    )

    # 🔧 Step 5: Sharpening
    kernel = np.array([[0, -1, 0], [-1, 9, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(thresh, -1, kernel)

    # 🔧 Step 6: Resize for clarity
    sharpened = cv2.resize(sharpened, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    return Image.fromarray(sharpened)


# ------------------------------------------------------------
# 🧠 SMART OCR EXTRACTION (FAST + FALLBACK)
# ------------------------------------------------------------
def extract_text(file_path: str) -> str:
    """Smart, fast, and parallel OCR extraction for PDFs and images."""
    import time
    start_time = time.time()

    text = ""
    ext = os.path.splitext(file_path)[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".pdf"}

    if ext not in allowed:
        raise ValueError(f"Unsupported file type: {ext}")

    try:
        # ------------------------------------------------------------
        # 📘 PDF Handling (Multi-page, with parallel OCR)
        # ------------------------------------------------------------
        if ext == ".pdf":
            pdf_document = fitz.open(file_path)
            page_count = len(pdf_document)
            print(f"📘 PDF detected: {page_count} pages")

            results = [""] * page_count  # maintain correct order

            def process_page(page_number: int):
                """Process a single page (thread-safe OCR worker)."""
                try:
                    page = pdf_document.load_page(page_number)
                    text_data = page.get_text("text").strip()

                    # ✅ Fast path for text-based pages
                    if len(text_data) > 80:
                        print(f"📄 Page {page_number + 1}: text-based extraction")
                        return page_number, text_data

                    # 🧠 OCR fallback for scanned pages
                    print(f"🖼️ Page {page_number + 1}: scanned — running OCR...")
                    pix = page.get_pixmap(dpi=200)
                    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
                    img_arr = cv2.equalizeHist(np.array(img))
                    img = Image.fromarray(img_arr)

                    ocr_text = pytesseract.image_to_string(
                        img, config="--oem 3 --psm 6", lang="eng"
                    )
                    del img, img_arr
                    gc.collect()
                    return page_number, ocr_text.strip()

                except Exception as e:
                    print(f"⚠️ OCR error on page {page_number + 1}: {e}")
                    return page_number, ""

            # 🧩 Parallel processing
            with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2)) as executor:
                futures = [executor.submit(process_page, i) for i in range(page_count)]
                for f in as_completed(futures):
                    idx, result_text = f.result()
                    results[idx] = result_text  # maintain page order

            pdf_document.close()
            text = " ".join(results)

        # ------------------------------------------------------------
        # 🖼️ IMAGE HANDLING
        # ------------------------------------------------------------
        else:
            img = Image.open(file_path).convert("L")
            img_arr = cv2.equalizeHist(np.array(img))
            img = Image.fromarray(img_arr)

            normal_text = pytesseract.image_to_string(
                img, config="--oem 3 --psm 6", lang="eng"
            )
            inverted_img = Image.fromarray(255 - np.array(img))
            inverted_text = pytesseract.image_to_string(
                inverted_img, config="--oem 3 --psm 6", lang="eng"
            )

            # Choose the cleaner result
            text = normal_text if len(normal_text) > len(inverted_text) else inverted_text
            del img, inverted_img
            gc.collect()

        # ------------------------------------------------------------
        # 🧹 Clean & Normalize
        # ------------------------------------------------------------
        text = re.sub(r'[^\x00-\x7F]+', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        elapsed = round(time.time() - start_time, 2)
        print(f"✅ OCR completed in {elapsed} seconds — {len(text)} chars extracted.")

    except Exception as e:
        print(f"❌ OCR Extraction Error: {e}")
        text = ""

    return text


# ------------------------------------------------------------
# 🧩 STRUCTURED PAN DATA EXTRACTION
# ------------------------------------------------------------
def extract_pan_details(text: str):
    """Extract structured PAN details."""
    structured_data = {}
    if not text.strip():
        return structured_data

    # PAN Number
    pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", text)
    if pan_match:
        structured_data["PAN Number"] = pan_match.group(0)

    # Date of Birth
    dob_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", text)
    if dob_match:
        structured_data["Date of Birth"] = dob_match.group(0)

    # Name (uppercase)
    lines = [line.strip() for line in re.split(r'[ \r\n]+', text) if line.strip()]
    name_candidates = [line for line in lines if re.match(r'^[A-Z ]{3,}$', line) and not re.search(r'\d', line)]
    if name_candidates:
        structured_data["Name"] = max(name_candidates, key=len)

    return structured_data


# ------------------------------------------------------------
# 🧩 STRUCTURED RESUME DATA EXTRACTION
# ------------------------------------------------------------
def extract_resume_details(text: str):
    """Extract key information from a resume."""
    structured_data = {}
    if not text.strip():
        return structured_data

    text = re.sub(r'\s+', ' ', text)

    # 👤 Name
    name_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})', text)
    if name_match:
        structured_data["Name"] = name_match.group(0)

    # 📧 Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if email_match:
        structured_data["Email"] = email_match.group(0)

    # 📞 Phone
    phone_match = re.search(r'\b\d{10}\b', text)
    if phone_match:
        structured_data["Phone"] = phone_match.group(0)

    # 📍 Location
    location_match = re.search(r'\b(Mangalore|Bangalore|Karnataka|Mumbai|Delhi|Chennai|Hyderabad|Pune)\b', text, re.IGNORECASE)
    if location_match:
        structured_data["Location"] = location_match.group(0)

    # 🎓 Education
    edu_match = re.search(r'(Bachelor|B\.E\.|BTech|B\.Tech|Master|MTech|M\.Tech|Engineering|Computer Science)', text, re.IGNORECASE)
    if edu_match:
        structured_data["Education"] = edu_match.group(0)

    # 🧠 Skills
    skills_keywords = ["Python", "Java", "C++", "Golang", "AWS", "Docker", "Kubernetes",
                       "Terraform", "SQL", "Git", "Azure", "PowerBI", "Tableau"]
    found_skills = [skill for skill in skills_keywords if re.search(skill, text, re.IGNORECASE)]
    if found_skills:
        structured_data["Skills"] = ", ".join(found_skills)

    return structured_data
