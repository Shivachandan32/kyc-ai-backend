# dashboard_api.py
from fastapi import APIRouter
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, Any
from db import audit_collection

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _fallback():
    return {
        "totals": {"uploads": 0},
        "risk_counts": {"Low": 0, "Medium": 0, "High": 0},
        "doc_counts": {"PAN Card": 0, "Aadhaar Card": 0, "Resume": 0, "Unknown": 0},
        "avg_completeness": 0.0,
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/metrics/summary")
def summary_metrics() -> Dict[str, Any]:
    """Last 200 uploads: risk mix, doc mix, average completeness."""
    if audit_collection is None:
        return _fallback()

    logs = list(audit_collection.find().sort("timestamp", -1).limit(200))
    if not logs:
        return _fallback()

    risk = Counter()
    doc = Counter()
    completeness_sum = 0.0
    counted = 0

    for log in logs:
        doc[log.get("document_type", "Unknown")] += 1
        ra = (log.get("risk_assessment") or {})
        risk[ra.get("Risk Level", "Unknown")] += 1

        # Prefer summary["Completeness (%)"], else parse risk_assessment["Completeness"] e.g. "86%"
        summ = log.get("summary") or {}
        if "Completeness (%)" in summ:
            completeness_sum += float(summ.get("Completeness (%)", 0) or 0)
            counted += 1
        else:
            comp_str = (ra.get("Completeness") or "").strip().rstrip("%")
            if comp_str.isdigit():
                completeness_sum += float(comp_str)
                counted += 1

    avg_completeness = round(completeness_sum / counted, 2) if counted else 0.0

    # Normalize keys
    risk_counts = {"Low": risk.get("Low", 0), "Medium": risk.get("Medium", 0), "High": risk.get("High", 0)}
    doc_counts = {
        "PAN Card": doc.get("PAN Card", 0),
        "Aadhaar Card": doc.get("Aadhaar Card", 0),
        "Resume": doc.get("Resume", 0),
        "Unknown": doc.get("Unknown", 0),
    }

    return {
        "totals": {"uploads": len(logs)},
        "risk_counts": risk_counts,
        "doc_counts": doc_counts,
        "avg_completeness": avg_completeness,
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/metrics/timeseries")
def timeseries(days: int = 14) -> Dict[str, Any]:
    """Daily upload counts & risk breakdown for the past N days."""
    if audit_collection is None:
        return {"days": [], "uploads": [], "low": [], "medium": [], "high": []}

    start = datetime.utcnow() - timedelta(days=days - 1)
    logs = list(audit_collection.find({"timestamp": {"$gte": start}}))

    # Prep buckets
    by_day = defaultdict(lambda: {"uploads": 0, "Low": 0, "Medium": 0, "High": 0})
    for log in logs:
        ts = log.get("timestamp") or datetime.utcnow()
        day = ts.date().isoformat()
        by_day[day]["uploads"] += 1
        rl = ((log.get("risk_assessment") or {}).get("Risk Level")) or "Unknown"
        if rl in ("Low", "Medium", "High"):
            by_day[day][rl] += 1

    # Build continuous series for each day
    days_list = [(start + timedelta(days=i)).date().isoformat() for i in range(days)]
    uploads = [by_day[d]["uploads"] for d in days_list]
    low = [by_day[d]["Low"] for d in days_list]
    medium = [by_day[d]["Medium"] for d in days_list]
    high = [by_day[d]["High"] for d in days_list]

    return {"days": days_list, "uploads": uploads, "low": low, "medium": medium, "high": high}


@router.get("/logs")
def legacy_logs_alias():
    """Backward compatibility: redirect to audit logs."""
    from app import get_audit_logs
    return get_audit_logs()
