# fraud_intelligence.py
import os
import requests
from deepface import DeepFace
from difflib import SequenceMatcher
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")


def analyze_image_sightengine(image_path: str) -> dict:
    """
    Analyze image authenticity using SightEngine API.
    Detects nudity, spoofing, or manipulation.
    """
    if not SIGHTENGINE_USER or not SIGHTENGINE_SECRET:
        return {"status": "error", "message": "SightEngine API keys missing or not set."}

    url = "https://api.sightengine.com/1.0/check.json"
    payload = {
        "models": "face-attributes,offensive,manipulated",
        "api_user": SIGHTENGINE_USER,
        "api_secret": SIGHTENGINE_SECRET,
    }

    try:
        with open(image_path, "rb") as f:
            response = requests.post(url, files={"media": f}, data=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return {"status": "ok", "data": data}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": f"API request failed: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}


def compare_faces(image1: str, image2: str) -> dict:
    """Compare two images to check if faces match using DeepFace."""
    try:
        result = DeepFace.verify(img1_path=image1, img2_path=image2, enforce_detection=False)
        return {
            "match": result.get("verified", False),
            "distance": result.get("distance", None),
            "model": result.get("model", "Unknown"),
            "status": "ok"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def detect_text_similarity(text1: str, text2: str) -> float:
    """Compare two text blocks for similarity ratio in percentage."""
    try:
        return round(SequenceMatcher(None, text1, text2).ratio() * 100, 2)
    except Exception:
        return 0.0


def fraud_summary_report(file_path: str, extracted_text: str) -> dict:
    """
    Unified fraud risk score from image + text analysis.
    Combines image manipulation detection and text red flag analysis.
    """
    fraud_score = 0
    report = {
        "image_analysis": {},
        "text_analysis": {},
        "fraud_score": 0,
        "overall_fraud_risk": "Low",
        "anomalies": [],
        "note": "OK"
    }

    # 🔍 1. Image-based fraud detection
    if file_path.lower().endswith((".jpg", ".jpeg", ".png")):
        img_result = analyze_image_sightengine(file_path)
        report["image_analysis"] = img_result

        if img_result.get("status") == "ok":
            data = img_result.get("data", {})
            if "manipulated" in str(data).lower() or "fake" in str(data).lower():
                fraud_score += 50
                report["anomalies"].append("Possible tampering detected by image analysis")
        else:
            report["note"] = img_result.get("message", "Image analysis unavailable")

    # 📄 2. Text-based fraud keyword detection
    suspicious_keywords = ["fake", "edited", "template", "duplicate", "tampered"]
    found_flags = [word for word in suspicious_keywords if word in extracted_text.lower()]
    if found_flags:
        report["text_analysis"]["flags"] = found_flags
        report["anomalies"].extend([f"Suspicious word found: '{w}'" for w in found_flags])
        fraud_score += 40

    # 🎯 3. Aggregate risk label
    report["fraud_score"] = min(fraud_score, 100)
    report["overall_fraud_risk"] = (
        "High" if fraud_score >= 70 else
        "Medium" if fraud_score >= 40 else
        "Low"
    )

    # 📘 4. Summary note
    if fraud_score >= 70:
        report["note"] = "High fraud likelihood. Requires manual verification."
    elif fraud_score >= 40:
        report["note"] = "Moderate fraud indicators detected."
    else:
        report["note"] = "No major anomalies found."

    return report
