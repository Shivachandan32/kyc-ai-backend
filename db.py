from pymongo import MongoClient
from datetime import datetime
import urllib.parse
import os

# ✅ MongoDB Configuration
username = "kycadmin"
password = urllib.parse.quote_plus("yourStrongPassword123")  # Replace with your actual password
cluster = "cluster0.zkivvqr.mongodb.net"

# ✅ Construct Connection URI
MONGO_URI = f"mongodb+srv://{username}:{password}@{cluster}/?appName=Cluster0"
DB_NAME = "kyc_ai"

# --------------------------------------------------------
# 🚀 Connect to MongoDB
# --------------------------------------------------------
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    db = client[DB_NAME]
    audit_collection = db["audit_logs"]
    client.admin.command("ping")  # test the connection
    print("✅ Connected to MongoDB successfully!")
except Exception as e:
    audit_collection = None
    print(f"❌ MongoDB connection failed: {e}")

# --------------------------------------------------------
# 🧾 Log Audit Entries
# --------------------------------------------------------
def log_audit_entry(file_name: str, document_type: str, summary: dict, risk_assessment: dict):
    """Insert an audit entry into MongoDB."""
    # ✅ FIX: Correct comparison (avoid bool() error)
    if audit_collection is None:
        print("⚠️ Skipping MongoDB logging (no active connection).")
        return

    try:
        entry = {
            "file_name": file_name,
            "document_type": document_type,
            "summary": summary,
            "risk_assessment": risk_assessment,
            "timestamp": datetime.utcnow()
        }
        audit_collection.insert_one(entry)
        print(f"📝 Audit log inserted for: {file_name}")
    except Exception as e:
        print(f"⚠️ Failed to log audit entry: {e}")
