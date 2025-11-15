from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from dotenv import load_dotenv          # <-- NEW
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from google.cloud import firestore
from firebase_admin import firestore  # ← ADD THIS# main.py

# -------------------------------------------------
# 1. Load .env (only needed in dev; prod uses real env vars)
# -------------------------------------------------
load_dotenv()          # reads backend/.env

app = FastAPI()

# -------------------------------------------------
# 2. CORS – adjust for production later
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# 3. Global Firestore client
# -------------------------------------------------
db = None
initialized = False


def init_firebase():
    global initialized, db
    if initialized:
        return

    sa_path = os.getenv("FIREBASE_SA_PATH")
    if not sa_path:
        raise RuntimeError(
            "FIREBASE_SA_PATH env var is missing. "
            "Set it in backend/.env to the path of your serviceAccountKey.json"
        )

    sa_path = os.path.abspath(os.path.join(os.path.dirname(__file__), sa_path))
    if not os.path.isfile(sa_path):
        raise FileNotFoundError(f"Firebase SA file not found: {sa_path}")

    cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred)

    # CORRECT WAY TO GET FIRESTORE CLIENT
    from firebase_admin import firestore
    db = firestore.client()

    initialized = True
    print(f"Firebase initialized with {sa_path}")  # ← Use this, not firestore.Client()
    initialized = True
    print(f"Firebase initialized with {sa_path}")

def verify_token(authorization_header: str):
    """Verify Firebase ID token from Authorization: Bearer <token>"""
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    id_token = authorization_header.split(" ", 1)[1]
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return decoded_token
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid ID token")


# -------------------------------------------------
# 4. Startup event – initialise Firebase once
# -------------------------------------------------
@app.on_event("startup")
def on_startup():
    init_firebase()


# -------------------------------------------------
# 5. Simple health-check route
# -------------------------------------------------
@app.get("/")
def root():
    return {"message": "FastAPI + Firebase backend is running!"}


# -------------------------------------------------
# 6. Your existing /save endpoint (unchanged logic)
# -------------------------------------------------
@app.post("/save")
async def save_entry(request: Request):
    init_firebase()          # safe to call again

    auth_header = request.headers.get("authorization")
    decoded = verify_token(auth_header)
    uid = decoded.get("uid")

    body = await request.json()
    asset_type = body.get("assetType")
    value = body.get("value")
    month = body.get("month")

    if not asset_type or value is None or not month:
        raise HTTPException(status_code=400, detail="Missing required fields")

    try:
        value = float(value)
    except Exception:
        raise HTTPException(status_code=400, detail="Value must be numeric")

    doc_ref = (
        db.collection("users")
        .document(uid)
        .collection("portfolio")
        .document()
    )
    doc_ref.set({
        "assetType": asset_type,
        "value": value,
        "month": month,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "createdBy": uid,
    })

    return {"status": "ok"}