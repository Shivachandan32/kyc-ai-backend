# app.py
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import shutil, os, time
from typing import Dict, Any

# ------------------------------
# Routers
# ------------------------------
from assistant import router as assistant_router
from dashboard_api import router as dashboard_router

# ------------------------------
# Core Components
# ------------------------------
from ocr_utils import extract_text, extract_pan_details, extract_resume_details
from ml_model import risk_classification
from db import log_audit_entry, audit_collection

# ------------------------------
# Optional modules (fallback safe)
# ------------------------------
try:
    from fraud_intelligence import fraud_summary_report
except Exception:
    def fraud_summary_report(file_path: str, extracted_text: str) -> Dict[str, Any]:
        return {"fraud_score": 0, "overall_fraud_risk": "Unknown", "note": "fraud_intelligence not installed"}

try:
    from fraud_detector import detect_tampering
except Exception:
    def detect_tampering(_path: str) -> Dict[str, Any]:
        return {"Fraud Risk": "Unknown", "Note": "fraud_detector not available"}

try:
    from xai import explain_risk
except Exception:
    def explain_risk(structured_data: dict, doc_type: str, risk: dict, extracted_text: str) -> Dict[str, Any]:
        return {
            "headline": "Basic heuristic explanation",
            "factors": [
                f"Document type: {doc_type}",
                f"Fields present: {len(structured_data)}",
                f"Risk level: {risk.get('Risk Level', 'Unknown')}",
            ],
        }

try:
    from confidence_engine import compute_field_confidence
except Exception:
    def compute_field_confidence(structured_data: dict, extracted_text: str) -> Dict[str, float]:
        return {k: (0.95 if str(v).strip() else 0.0) for k, v in structured_data.items()}


# --------------------------------------------------------
# 🧠 Smart Summary Generator
# --------------------------------------------------------
def generate_summary(structured_data: dict, doc_type: str) -> dict:
    total_fields = len(structured_data)
    filled_fields = sum(1 for v in structured_data.values() if v and str(v).strip())

    if total_fields > 0:
        completeness = (filled_fields / total_fields) * 100
        confidence = "High" if completeness >= 80 else ("Medium" if completeness >= 50 else "Low")
    else:
        completeness = 0
        confidence = "Low"

    summary = {
        "Document Type": doc_type,
        "Fields Extracted": total_fields,
        "Filled Fields": filled_fields,
        "Completeness (%)": round(completeness, 2),
        "Confidence": confidence,
    }

    if doc_type == "Resume":
        summary["Detected Skills"] = structured_data.get("Skills", "N/A")
    elif doc_type == "PAN Card" and "PAN Number" not in structured_data:
        summary["Note"] = "PAN number missing or unreadable"
    elif doc_type == "Aadhaar Card":
        summary["Note"] = "Aadhaar extraction module pending"

    return summary


# --------------------------------------------------------
# 🔍 Document Type Detection
# --------------------------------------------------------
def detect_document_type(text: str) -> str:
    if not text or len(text.strip()) < 10:
        return "Unknown"
    t = text.lower()
    if "income tax department" in t or "permanent account number" in t:
        return "PAN Card"
    if "aadhaar" in t or "uidai" in t:
        return "Aadhaar Card"
    if any(w in t for w in ["education", "experience", "skills", "projects", "intern", "github", "linkedin", "bachelor", "engineer"]):
        return "Resume"
    return "Unknown"


# --------------------------------------------------------
# 🚀 FastAPI App Setup
# --------------------------------------------------------
APP_VERSION = "1.7.2"

app = FastAPI(
    title="KYC-AI OCR API",
    description="AI-powered OCR API with Explainable Risk, Confidence, and Fraud Intelligence",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(dashboard_router)
app.include_router(assistant_router)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --------------------------------------------------------
# 🌐 Root & Health Endpoints
# --------------------------------------------------------
@app.get("/")
def root():
    return {"message": "✅ KYC-AI Backend is running successfully!", "version": APP_VERSION}


@app.get("/health")
def health():
    """Safe health check (no bool casting)."""
    mongo_status = False
    try:
        mongo_status = audit_collection is not None
    except Exception:
        mongo_status = False

    return {
        "status": "ok",
        "mongo": mongo_status,
        "version": APP_VERSION
    }


@app.get("/version")
def version():
    return {"version": APP_VERSION}


# --------------------------------------------------------
# 🧾 Upload Endpoint
# --------------------------------------------------------
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    t0 = time.time()
    try:
        # Save file
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # OCR Extraction
        extracted_text = extract_text(file_path).strip()
        if not extracted_text:
            return {
                "document_type": "Unknown",
                "extracted_text": "",
                "structured_data": {},
                "summary": {"Fields Extracted": 0, "Confidence": "Low"},
                "risk_assessment": {"Risk Level": "High", "Reason": "Unreadable file"},
                "fraud_detection": {"Fraud Risk": "Unknown"},
                "confidence_scores": {},
                "explanation": {"headline": "Unreadable or blank file."},
                "elapsed_sec": round(time.time() - t0, 2),
            }

        doc_type = detect_document_type(extracted_text)
        if doc_type == "PAN Card":
            structured_data = extract_pan_details(extracted_text)
        elif doc_type == "Aadhaar Card":
            structured_data = {"Document": "Aadhaar Card", "Note": "Module pending."}
        elif doc_type == "Resume":
            structured_data = extract_resume_details(extracted_text)
        else:
            structured_data = {"Document": "Unknown"}

        summary = generate_summary(structured_data, doc_type)
        risk_assessment = risk_classification(structured_data, doc_type)
        explanation = explain_risk(structured_data, doc_type, risk_assessment, extracted_text)
        confidence_scores = compute_field_confidence(structured_data, extracted_text)
        fraud_result = fraud_summary_report(file_path, extracted_text)

        if file_path.lower().endswith((".jpg", ".jpeg", ".png")):
            fraud_result["tamper_analysis"] = detect_tampering(file_path)

        try:
            log_audit_entry(file.filename, doc_type, summary, risk_assessment)
        except Exception as e:
            print(f"⚠️ Audit logging skipped: {e}")

        return {
            "document_type": doc_type,
            "extracted_text": extracted_text,
            "structured_data": structured_data,
            "summary": summary,
            "risk_assessment": risk_assessment,
            "fraud_detection": fraud_result,
            "confidence_scores": confidence_scores,
            "explanation": explanation,
            "elapsed_sec": round(time.time() - t0, 2),
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"❌ Internal error: {str(e)}"}
        )


# --------------------------------------------------------
# 📜 Audit Logs
# --------------------------------------------------------
@app.get("/audit/")
def get_audit_logs():
    try:
        if audit_collection is None:
            return {"error": "MongoDB not connected"}
        logs = list(audit_collection.find().sort("timestamp", -1).limit(10))
        for log in logs:
            log["_id"] = str(log["_id"])
        return {"count": len(logs), "logs": logs}
    except Exception as e:
        return {"error": f"❌ Failed to fetch audit logs: {e}"}


# --------------------------------------------------------
# 🔥 Render Entrypoint
# --------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
