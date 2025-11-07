# assistant.py
from fastapi import APIRouter, Body
from datetime import datetime
import re
from db import audit_collection

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])

# --------------------------------------------------------
# 🧠 Rule-based AI Assistant for KYC Guidance
# --------------------------------------------------------
@router.post("/query")
async def ai_assistant(query: str = Body(..., embed=True)):
    """AI Assistant endpoint for user help & smart feedback."""
    try:
        query_lower = query.lower().strip()
        response = "I'm not sure I understand. Could you clarify your question?"

        # ✅ Contextual logic
        if "risk" in query_lower:
            last_entry = audit_collection.find_one(sort=[("timestamp", -1)])
            if last_entry:
                risk = last_entry.get("risk_assessment", {}).get("Risk Level", "Unknown")
                reason = "based on incomplete or inconsistent fields." if risk != "Low" else "because all fields were verified and consistent."
                response = f"Your most recent document has a **{risk}** risk level {reason}"
            else:
                response = "No recent uploads found in the system."

        elif "upload" in query_lower or "file" in query_lower:
            response = "You can upload PAN, Aadhaar, or Resume documents. Make sure images are clear and in .jpg, .png, or .pdf format."

        elif "pan" in query_lower:
            response = (
                "A PAN card should clearly show the PAN number, name, and date of birth. "
                "If these are not detected, try rescanning under better lighting or higher resolution."
            )

        elif "aadhaar" in query_lower:
            response = (
                "Aadhaar OCR is still under development, but you can still upload it. "
                "Ensure your Aadhaar number and name are clearly visible for better results."
            )

        elif "resume" in query_lower:
            response = (
                "Resume OCR extracts name, contact, education, and skills. "
                "You can improve accuracy by uploading a PDF or text-based resume rather than a photo."
            )

        elif "improve" in query_lower or "accuracy" in query_lower:
            response = (
                "To improve accuracy: use high-resolution images, proper lighting, and straight alignment. "
                "Avoid blurry photos or handwritten text."
            )

        elif "explain" in query_lower or "why" in query_lower:
            response = (
                "The system evaluates extracted data completeness and detects anomalies like invalid formats. "
                "A high risk means missing data or irregularities; a low risk means consistent and verified details."
            )

        elif "help" in query_lower or "what can you do" in query_lower:
            response = (
                "I can help explain your verification results, risk levels, and guide you on improving OCR accuracy. "
                "Try asking: 'Why is my risk high?' or 'How to improve OCR quality?'"
            )

        # ✅ Log AI interaction (optional)
        audit_collection.insert_one({
            "type": "assistant_query",
            "query": query,
            "response": response,
            "timestamp": datetime.utcnow()
        })

        return {"query": query, "response": response}

    except Exception as e:
        return {"error": f"❌ Failed to process AI query: {str(e)}"}
