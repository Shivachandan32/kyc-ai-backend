# xai.py — Explainable AI Engine for KYC-AI
from typing import Dict, List, Optional
import re

# Regex patterns
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
DOB_REGEX = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

def _present(v) -> bool:
    """Check if a value exists and is non-empty."""
    return v is not None and str(v).strip() != ""

def _missing(keys: List[str], data: Dict) -> List[str]:
    """Return missing keys from data."""
    return [k for k in keys if not _present(data.get(k))]

def explain_risk(
    structured: Dict,
    doc_type: str,
    risk_assessment: Dict,
    extracted_text: Optional[str] = None
) -> Dict:
    """
    Generate human-readable explanations for document risk.
    No external dependencies or randomness — deterministic output.
    """

    reasons: List[str] = []
    suggestions: List[str] = []

    # 🧾 1) Completeness check
    comp_pct_str = str(risk_assessment.get("Completeness", "0")).replace("%", "")
    try:
        comp_pct = int(float(comp_pct_str))
    except ValueError:
        comp_pct = 0

    if comp_pct >= 90:
        reasons.append("Most mandatory fields are present.")
    elif comp_pct >= 60:
        reasons.append("Some required fields are missing.")
        suggestions.append("Provide the missing fields listed below.")
    else:
        reasons.append("Many fields are missing or unreadable.")
        suggestions.append("Upload a higher-quality image or text-based PDF.")

    # 📄 2) Document-specific logic
    t = (doc_type or "").strip().lower()

    if t == "pan card":
        required = ["Name", "PAN Number", "Date of Birth"]
        missing = _missing(required, structured)
        if missing:
            reasons.append(f"Missing key PAN fields: {', '.join(missing)}.")
        else:
            reasons.append("All key PAN fields were successfully detected.")

        pan = structured.get("PAN Number")
        if _present(pan) and not PAN_REGEX.match(pan):
            reasons.append("PAN format appears invalid.")
            suggestions.append("Ensure PAN follows format: 5 letters + 4 digits + 1 letter (e.g., ABCDE1234F).")

        dob = structured.get("Date of Birth")
        if _present(dob) and not DOB_REGEX.search(dob):
            reasons.append("Date of Birth format appears unusual.")
            suggestions.append("Use DD/MM/YYYY format (e.g., 07/11/1999).")

    elif t == "aadhaar card":
        reasons.append("Basic Aadhaar checks applied.")
        if structured.get("Aadhaar Number") and "XXXX" in structured.get("Aadhaar Number"):
            reasons.append("Masked Aadhaar number detected.")
            suggestions.append("Provide a full, non-masked Aadhaar number for verification.")
        suggestions.append("Ensure the front side of Aadhaar is uploaded for accurate parsing.")

    elif t == "resume":
        must_have = ["Name", "Email", "Phone"]
        miss = _missing(must_have, structured)
        if miss:
            reasons.append(f"Resume basics missing: {', '.join(miss)}.")
            suggestions.append("Ensure name, email, and phone number are visible on the first page.")
        else:
            reasons.append("Resume key contact details successfully extracted.")
        if _present(structured.get("Skills")):
            reasons.append("Skills section detected and parsed.")
        else:
            suggestions.append("Add a 'Skills' section listing your core technologies.")

    # ⚠️ 3) Detected anomalies (if any)
    anoms = risk_assessment.get("Detected Anomalies") or []
    if isinstance(anoms, list) and anoms and anoms[0] != "None":
        reasons.append("Detected anomalies: " + ", ".join(anoms))
        suggestions.append("Correct the highlighted anomalies and re-upload.")

    # 🧠 4) OCR sanity check
    if extracted_text is not None and len(extracted_text.strip()) < 40:
        reasons.append("Very low text content — likely a cropped or noisy image.")
        suggestions.append("Use a straight, well-lit photo or a digital PDF.")

    # 🏁 5) Generate headline
    risk_level = risk_assessment.get("Risk Level", "Unknown")
    if reasons:
        headline = f"Risk Level: {risk_level} — Key factors: " + "; ".join(reasons[:3])
    else:
        headline = f"Risk Level: {risk_level} — No anomalies detected."

    # ✅ Return explainable structure
    return {
        "headline": headline,
        "risk_level": risk_level,
        "reasons": reasons or ["No anomalies detected."],
        "suggestions": suggestions or ["No corrective actions needed."]
    }
