# fraud_detector.py
import cv2
import numpy as np
from PIL import Image
import imagehash
import os

def detect_tampering(image_path: str) -> dict:
    """
    Detects potential tampering in scanned documents using image analysis.
    Returns confidence score + anomalies.
    """
    try:
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # ✅ Step 1: Detect unusual edges or splices
        edges = cv2.Canny(gray, 100, 200)
        edge_density = np.mean(edges > 0)

        # ✅ Step 2: Detect brightness inconsistency (Photoshop artifacts)
        blur = cv2.GaussianBlur(gray, (15, 15), 0)
        diff = cv2.absdiff(gray, blur)
        brightness_var = np.std(diff)

        # ✅ Step 3: Compute hash for uniformity
        phash = imagehash.phash(Image.open(image_path))
        hash_val = str(phash)

        anomalies = []
        if edge_density > 0.15:
            anomalies.append("High edge density (possible tampering)")
        if brightness_var > 35:
            anomalies.append("Brightness variation suggests editing")

        risk_score = min(100, int((edge_density * 500) + brightness_var))
        risk_label = (
            "Low" if risk_score < 40 else
            "Medium" if risk_score < 70 else
            "High"
        )

        return {
            "Fraud Risk": risk_label,
            "Tampering Confidence (%)": risk_score,
            "Anomalies": anomalies or ["No visual anomalies detected"],
            "Image Hash": hash_val
        }

    except Exception as e:
        return {"error": f"Fraud detection failed: {e}"}
