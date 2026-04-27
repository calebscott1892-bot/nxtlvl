import logging
import os
import secrets
import time
from collections import defaultdict
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles

try:
    from nxtlvl.booking import (
        StatusUpdate,
        list_bookings,
        public_router,
        update_status,
    )
except ModuleNotFoundError:
    from booking import (
        StatusUpdate,
        list_bookings,
        public_router,
        update_status,
    )

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("nxtlvl")

# ── API key for admin endpoints ────────────────────────
ADMIN_KEY = os.environ.get("NXTLVL_ADMIN_KEY", "")
if not ADMIN_KEY:
    ADMIN_KEY = secrets.token_urlsafe(32)
    logger.warning("No NXTLVL_ADMIN_KEY set — generated ephemeral key: %s", ADMIN_KEY)

api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def require_admin_key(key: str = Depends(api_key_header)):
    if not key or not secrets.compare_digest(key, ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing admin key")


# ── Rate limiting (in-memory, per-IP) ─────────────────
RATE_WINDOW = 60  # seconds
RATE_MAX = 10     # max booking requests per window
_rate_store: dict[str, list[float]] = defaultdict(list)

app = FastAPI(title="NXTLVL")


@app.middleware("http")
async def block_sensitive_files(request: Request, call_next):
    """Prevent the static-file mount from exposing source code, database, or config."""
    path = request.url.path.lower()
    blocked_ext = (".py", ".pyc", ".db", ".db-wal", ".db-shm", ".sqlite", ".env")
    blocked_prefix = ("/__pycache__", "/.git", "/.env")
    if any(path.endswith(ext) for ext in blocked_ext) or any(
        path.startswith(p) for p in blocked_prefix
    ):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return response


@app.middleware("http")
async def rate_limit_bookings(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/bookings":
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
        if len(_rate_store[ip]) >= RATE_MAX:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )
        _rate_store[ip].append(now)
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    logger.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code, (time.time() - start) * 1000)
    return response


# ── Health check ───────────────────────────────────────
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "database": "postgres" if os.environ.get("DATABASE_URL", "").strip() else "sqlite-fallback",
    }


# ── Public booking routes (create + availability) ─────
app.include_router(public_router)


# ── Admin routes (protected with API key) ─────────────
@app.get("/bookings", dependencies=[Depends(require_admin_key)], tags=["admin"])
def admin_list_bookings():
    return list_bookings()


@app.patch("/bookings/{booking_id}/status", dependencies=[Depends(require_admin_key)], tags=["admin"])
def admin_update_status(booking_id: int, body: StatusUpdate):
    return update_status(booking_id, body)


# ── Static files (must be last) ───────────────────────
app.mount("/", StaticFiles(directory=str(Path(__file__).parent), html=True), name="static")
