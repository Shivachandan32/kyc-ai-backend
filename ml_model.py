# --------------------------------------------------------
# 📊 ml_model.py — AI-based Risk Scoring & Data Sanity Engine
# --------------------------------------------------------
import re

# -------------------------------------------
# 🧮 Completeness Scoring
# -------------------------------------------
def calculate_completeness_score(data: dict) -> int:
    """Simple heuristic scoring system based on how complete the structured data is."""
    if not data:
        return 0

    total_fields = len(data)
    non_empty_fields = sum(1 for v in data.values() if v and str(v).strip())
    return int((non_empty_fields / total_fields) * 100) if total_fields else 0


# -------------------------------------------
# 🕵️ Anomaly Detection
# -------------------------------------------
def detect_anomalies(data: dict) -> list:
    """Performs sanity checks and identifies suspicious patterns."""
    anomalies = []

    # PAN pattern check
    if "PAN Number" in data:
        if not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", str(data["PAN Number"])):
            anomalies.append("Invalid PAN format")

    # DOB format check
    if "Date of Birth" in data:
        if not re.match(r"\b\d{2}/\d{2}/\d{4}\b", str(data["Date of Birth"])):
            anomalies.append("Suspicious DOB format")

    # Email pattern check
    if "Email" in data:
        if not re.match(r"[^@]+@[^@]+\.[^@]+", str(data["Email"])):
            anomalies.append("Invalid Email format")

    # Phone number pattern check
    if "Phone" in data:
        if not re.match(r"^\d{10}$", str(data["Phone"])):
            anomalies.append("Invalid Phone number")

    return anomalies


# -------------------------------------------
# 🧠 AI-style Risk Classification
# -------------------------------------------
def risk_classification(data: dict, document_type: str) -> dict:
    """
    Classifies document verification risk based on data completeness
    and anomalies detected during extraction.
    """
    completeness = calculate_completeness_score(data)
    anomalies = detect_anomalies(data)

    # Core risk logic
    if completeness >= 80 and not anomalies:
        risk_level = "Low"
        reason = "Document appears complete and valid."
    elif completeness >= 50:
        risk_level = "Medium"
        reason = "Partial or inconsistent data found."
    else:
        risk_level = "High"
        reason = "Significant missing fields or invalid data patterns."

    return {
        "Document Type": document_type,
        "Completeness": f"{completeness}%",
        "Detected Anomalies": anomalies or ["None"],
        "Risk Level": risk_level,
        "Reason": reason
    }
