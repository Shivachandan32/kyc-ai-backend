# fraud_intelligence.py
import os
import requests
from deepface import DeepFace
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

SIGHTENGINE_USER = os.getenv("SIGHTENGINE_USER")
SIGHTENGINE_SECRET = os.getenv("SIGHTENGINE_SECRET")


def analyze_image_sightengine(image_path: str) -> dict:
    """
    Analyze image authenticity using SightEngine API.
    Detects nudity, spoofing, or manipulation.
    """
    if not SIGHTENGINE_USER or not SIGHTENGINE_SECRET:
        return {"status": "error", "message": "SightEngine API keys missing."}

    url = "https://api.sightengine.com/1.0/check.json"
    files = {"media": open(image_path, "rb")}
    payload = {
        "models": "face-attributes,offensive,manipulated",
        "api_user": SIGHTENGINE_USER,
        "api_secret": SIGHTENGINE_SECRET,
    }

    try:
        response = requests.post(url, files=files, data=payload)
        data = response.json()
        return data
    except Exception as e:
        return {"status": "error", "message": str(e)}


def compare_faces(image1: str, image2: str) -> dict:
    """Compare two images to check if faces match."""
    try:
        result = DeepFace.verify(img1_path=image1, img2_path=image2, enforce_detection=False)
        return {
            "match": result["verified"],
            "distance": result["distance"],
            "model": result["model"],
        }
    except Exception as e:
        return {"error": str(e)}


def detect_text_similarity(text1: str, text2: str) -> float:
    """Compare two texts for similarity ratio."""
    return round(SequenceMatcher(None, text1, text2).ratio() * 100, 2)


def fraud_summary_report(file_path: str, extracted_text: str) -> dict:
    """
    Unified fraud risk score from image + text analysis.
    """
    fraud_score = 0
    report = {"image_analysis": {}, "text_analysis": {}, "overall_fraud_risk": "Low"}

    # 🔍 1. Image-based fraud detection
    if file_path.lower().endswith((".jpg", ".jpeg", ".png")):
        img_result = analyze_image_sightengine(file_path)
        report["image_analysis"] = img_result

        if "media" in img_result and "fake" in str(img_result).lower():
            fraud_score += 60

    # 📄 2. Text-based consistency check
    keywords = ["fake", "edited", "template", "duplicate"]
    text_flags = [word for word in keywords if word in extracted_text.lower()]
    if text_flags:
        report["text_analysis"]["flags"] = text_flags
        fraud_score += 40

    # 🎯 Final risk label
    report["fraud_score"] = fraud_score
    report["overall_fraud_risk"] = (
        "High" if fraud_score >= 70 else "Medium" if fraud_score >= 40 else "Low"
    )

    return report
