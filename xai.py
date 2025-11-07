# xai.py
from typing import Dict, List
import re

PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
DOB_REGEX = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

def _present(v) -> bool:
    return v is not None and str(v).strip() != ""

def _missing(keys: List[str], data: Dict) -> List[str]:
    return [k for k in keys if not _present(data.get(k))]

def explain_risk(structured: Dict, doc_type: str, risk_assessment: Dict, extracted_text: str | None = None) -> Dict:
    """
    Produce human-friendly reasons for the risk score + actionable suggestions.
    Keeps it deterministic (no LLM).
    """
    reasons: List[str] = []
    suggestions: List[str] = []

    # 1) Generic completeness signal
    comp_pct_str = risk_assessment.get("Completeness", "0%").replace("%", "")
    try:
        comp_pct = int(float(comp_pct_str))
    except:
        comp_pct = 0

    if comp_pct >= 90:
        reasons.append("Most mandatory fields are present.")
    elif comp_pct >= 60:
        reasons.append("Some required fields are missing.")
        suggestions.append("Provide the missing fields highlighted below.")
    else:
        reasons.append("Many fields are missing or unreadable.")
        suggestions.append("Re-upload a higher quality scan or a text PDF if available.")

    # 2) Document-type specific checks
    t = (doc_type or "").lower()

    if t == "pan card":
        required = ["Name", "PAN Number", "Date of Birth"]
        missing = _missing(required, structured)
        if missing:
            reasons.append(f"Missing key PAN fields: {', '.join(missing)}.")
        else:
            reasons.append("All key PAN fields were detected.")

        pan = structured.get("PAN Number")
        if _present(pan) and not PAN_REGEX.match(pan):
            reasons.append("PAN format looks invalid.")
            suggestions.append("Ensure PAN is 5 letters, 4 digits, and 1 letter (e.g., ABCDE1234F).")

        dob = structured.get("Date of Birth")
        if _present(dob) and not DOB_REGEX.search(dob):
            reasons.append("DOB format appears unusual.")
            suggestions.append("Use DD/MM/YYYY format (e.g., 07/11/1999).")

    elif t == "aadhaar card":
        reasons.append("Aadhaar parsing is basic; only coarse checks applied.")
        suggestions.append("Add clearer front-side Aadhaar image for better extraction.")
    
    elif t == "resume":
        # Helpful resume-centric hints
        must_have = ["Name", "Email", "Phone"]
        miss = _missing(must_have, structured)
        if miss:
            reasons.append(f"Resume basics missing: {', '.join(miss)}.")
            suggestions.append("Ensure your name, email and 10-digit phone are clearly visible on the first page.")
        else:
            reasons.append("Resume key contact details detected.")
        if _present(structured.get("Skills")):
            reasons.append("Technical skills detected successfully.")
        else:
            suggestions.append("Add a dedicated 'Skills' section with technologies in a comma-separated line.")

    # 3) Anomalies passed from the risk function
    anoms = risk_assessment.get("Detected Anomalies") or []
    if isinstance(anoms, list) and anoms and anoms[0] != "None":
        reasons.append("Detected anomalies: " + ", ".join(anoms) + ".")
        suggestions.append("Correct the highlighted anomalies and re-upload.")

    # 4) OCR sanity
    if extracted_text is not None and len(extracted_text) < 40:
        reasons.append("Very low text content, likely a noisy or cropped scan.")
        suggestions.append("Try a straight, well-lit photo or export as a text PDF.")

    # 5) Final headline
    headline = f"Risk is {risk_assessment.get('Risk Level', 'Unknown')} because " + (
        ", ".join(reasons) if reasons else "the document quality and fields are inconclusive."
    )

    return {
        "headline": headline,
        "reasons": reasons,
        "suggestions": suggestions
    }
