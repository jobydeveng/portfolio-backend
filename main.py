import os
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth, firestore

# -------------------------------------------------
# 1. Load .env (dev only)
# -------------------------------------------------
load_dotenv()

app = FastAPI()

# -------------------------------------------------
# 2. CORS – allow Vercel + localhost
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://portfolio-frontend-new.vercel.app",   # <-- YOUR VERCEL DOMAIN
        # "https://*"  # ← use only for quick testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# 3. Firebase init (service-account from Render secret file)
# -------------------------------------------------
db = None
initialized = False

def init_firebase():
    global db, initialized
    if initialized:
        return

    # Render secret file path (set in Render dashboard)
    sa_path = os.getenv("FIREBASE_SA_PATH", "/etc/secrets/serviceAccountKey.json")

    if not os.path.isfile(sa_path):
        raise FileNotFoundError(f"Firebase SA file not found: {sa_path}")

    cred = credentials.Certificate(sa_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    initialized = True
    print(f"Firebase initialized with {sa_path}")

# -------------------------------------------------
# 4. Token verification
# -------------------------------------------------
def verify_token(authorization_header: str):
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )
    id_token = authorization_header.split(" ", 1)[1]
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ID token",
        ) from exc

# -------------------------------------------------
# 5. Startup
# -------------------------------------------------
@app.on_event("startup")
def on_startup():
    init_firebase()

# -------------------------------------------------
# 6. Health check
# -------------------------------------------------
@app.get("/")
def root():
    return {"message": "FastAPI + Firebase backend is running!"}

# -------------------------------------------------
# 7. Save endpoint
# -------------------------------------------------
@app.post("/save")
async def save_entry(request: Request):
    # Firebase is already init-ed on startup
    auth_header = request.headers.get("authorization")
    decoded = verify_token(auth_header)
    uid = decoded["uid"]

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
    doc_ref.set(
        {
            "assetType": asset_type,
            "value": value,
            "month": month,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "createdBy": uid,
        }
    )
    return {"status": "ok"}