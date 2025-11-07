# confidence_engine.py
import re
from typing import Dict

def compute_field_confidence(structured_data: Dict, extracted_text: str) -> Dict:
    """Assign confidence score (0–100%) to each extracted field."""
    confidence = {}
    text = extracted_text.lower()

    for key, value in structured_data.items():
        if not value:
            confidence[key] = 0
            continue

        val = str(value).lower()
        score = 60  # base confidence

        # Higher if found verbatim
        if val in text:
            score += 20

        # Regex-based boosts
        if re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", value):
            score += 15  # PAN format
        if re.match(r"\b\d{2}/\d{2}/\d{4}\b", value):
            score += 10  # DOB pattern
        if "@" in value and "." in value:
            score += 10  # email

        # Cap at 100
        confidence[key] = min(score, 100)

    return confidence
