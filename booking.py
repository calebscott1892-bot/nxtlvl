"""
NXTLVL booking API.

Production uses Supabase/Postgres when DATABASE_URL is set.
Local development falls back to bookings.db SQLite.
"""

import os
import re
import sqlite3
from calendar import monthrange
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, field_validator, model_validator

try:
    import psycopg
    from psycopg import errors as pg_errors
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    pg_errors = None
    dict_row = None

try:
    from nxtlvl.notifications import notify_new_booking
except ModuleNotFoundError:
    from notifications import notify_new_booking

router = APIRouter(prefix="/bookings", tags=["bookings"])
public_router = router

DB_PATH = Path(__file__).parent / "bookings.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = DATABASE_URL.lower().startswith(("postgres://", "postgresql://"))

VALID_TIMES = {"08:00", "09:00", "10:00", "11:00", "12:00", "13:00"}
WEEKDAYS = {0, 1, 2, 3, 4}
BUSINESS_TZ = ZoneInfo("America/Chicago")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_RE = re.compile(r"^[-0-9+() ]{7,20}$")


def _today():
    return datetime.now(BUSINESS_TZ).date()


def _postgres_url() -> str:
    if "sslmode=" in DATABASE_URL:
        return DATABASE_URL
    separator = "&" if "?" in DATABASE_URL else "?"
    return f"{DATABASE_URL}{separator}sslmode=require"


@contextmanager
def _get_db():
    if USE_POSTGRES:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed")
        conn = psycopg.connect(
            _postgres_url(),
            row_factory=dict_row,
            prepare_threshold=None,
        )
    else:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _sql(sqlite_sql: str, postgres_sql: str | None = None) -> str:
    if USE_POSTGRES:
        return postgres_sql or sqlite_sql.replace("?", "%s")
    return sqlite_sql


def _init_db():
    with _get_db() as db:
        if USE_POSTGRES:
            db.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id             SERIAL PRIMARY KEY,
                    name           TEXT NOT NULL,
                    email          TEXT NOT NULL,
                    phone          TEXT NOT NULL,
                    session_type   TEXT NOT NULL CHECK(session_type IN ('solo','group')),
                    group_size     INTEGER DEFAULT 1,
                    preferred_date TEXT NOT NULL,
                    preferred_time TEXT NOT NULL,
                    notes          TEXT DEFAULT '',
                    status         TEXT DEFAULT 'pending' CHECK(status IN ('pending','confirmed','cancelled')),
                    created_at     TIMESTAMPTZ DEFAULT now()
                )
            """)
        else:
            db.execute("""
                CREATE TABLE IF NOT EXISTS bookings (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name           TEXT NOT NULL,
                    email          TEXT NOT NULL,
                    phone          TEXT NOT NULL,
                    session_type   TEXT NOT NULL CHECK(session_type IN ('solo','group')),
                    group_size     INTEGER DEFAULT 1,
                    preferred_date TEXT NOT NULL,
                    preferred_time TEXT NOT NULL,
                    notes          TEXT DEFAULT '',
                    status         TEXT DEFAULT 'pending' CHECK(status IN ('pending','confirmed','cancelled')),
                    created_at     TEXT DEFAULT (datetime('now'))
                )
            """)

        db.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_active_booking_slot
            ON bookings (preferred_date, preferred_time)
            WHERE status != 'cancelled'
        """)


_init_db()


class BookingCreate(BaseModel):
    name: str
    email: str
    phone: str
    session_type: str
    group_size: int = 1
    preferred_date: str
    preferred_time: str
    notes: str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not EMAIL_RE.match(v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not PHONE_RE.match(v):
            raise ValueError("Invalid phone number format")
        return v

    @field_validator("session_type")
    @classmethod
    def validate_session_type(cls, v: str) -> str:
        if v not in ("solo", "group"):
            raise ValueError("session_type must be 'solo' or 'group'")
        return v

    @field_validator("preferred_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if v not in VALID_TIMES:
            raise ValueError(f"preferred_time must be one of: {', '.join(sorted(VALID_TIMES))}")
        return v

    @field_validator("preferred_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            d = datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("preferred_date must be YYYY-MM-DD")
        if d.weekday() not in WEEKDAYS:
            raise ValueError("preferred_date must be Monday-Friday")
        if d.date() < _today():
            raise ValueError("preferred_date cannot be in the past")
        return v

    @field_validator("group_size")
    @classmethod
    def validate_group_size(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("group_size must be 1-5")
        return v

    @model_validator(mode="after")
    def validate_group_size_matches_type(self):
        if self.session_type == "group" and self.group_size < 3:
            raise ValueError("group sessions require group_size of 3-5")
        if self.session_type == "solo" and self.group_size != 1:
            raise ValueError("solo sessions must have group_size of 1")
        return self


class StatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("confirmed", "cancelled"):
            raise ValueError("status must be 'confirmed' or 'cancelled'")
        return v


@router.post("", status_code=201)
def create_booking(body: BookingCreate, background_tasks: BackgroundTasks):
    """Submit a new booking request."""
    with _get_db() as db:
        existing = db.execute(
            _sql("SELECT id FROM bookings WHERE preferred_date = ? AND preferred_time = ? AND status != 'cancelled'"),
            (body.preferred_date, body.preferred_time),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="That time slot is already booked")

        insert_params = (
            body.name,
            body.email,
            body.phone,
            body.session_type,
            body.group_size,
            body.preferred_date,
            body.preferred_time,
            body.notes,
        )

        try:
            if USE_POSTGRES:
                cursor = db.execute(
                    """INSERT INTO bookings (name, email, phone, session_type, group_size, preferred_date, preferred_time, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       RETURNING id""",
                    insert_params,
                )
                booking_id = cursor.fetchone()["id"]
            else:
                cursor = db.execute(
                    """INSERT INTO bookings (name, email, phone, session_type, group_size, preferred_date, preferred_time, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    insert_params,
                )
                booking_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="That time slot is already booked")
        except Exception as exc:
            if pg_errors and isinstance(exc, pg_errors.UniqueViolation):
                raise HTTPException(status_code=400, detail="That time slot is already booked")
            raise

    background_tasks.add_task(
        notify_new_booking,
        {
            "id": booking_id,
            "name": body.name,
            "email": body.email,
            "phone": body.phone,
            "session_type": body.session_type,
            "group_size": body.group_size,
            "preferred_date": body.preferred_date,
            "preferred_time": body.preferred_time,
            "notes": body.notes,
        },
    )
    return {"id": booking_id, "status": "pending"}


@router.get("/availability")
def get_availability(month: str):
    """Return available slots for every weekday in the given month."""
    try:
        year, mon = month.split("-")
        year, mon = int(year), int(mon)
        if mon < 1 or mon > 12:
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")

    _, days_in_month = monthrange(year, mon)
    today = _today()

    with _get_db() as db:
        rows = db.execute(
            _sql("SELECT preferred_date, preferred_time FROM bookings WHERE preferred_date LIKE ? AND status != 'cancelled'"),
            (f"{year:04d}-{mon:02d}-%",),
        ).fetchall()

    booked = {}
    for row in rows:
        booked.setdefault(row["preferred_date"], set()).add(row["preferred_time"])

    result = []
    for day in range(1, days_in_month + 1):
        d = datetime(year, mon, day)
        if d.weekday() not in WEEKDAYS:
            continue
        if d.date() < today:
            continue
        date_str = d.strftime("%Y-%m-%d")
        taken = booked.get(date_str, set())
        result.append({"date": date_str, "slots": sorted(VALID_TIMES - taken)})

    return result


@router.get("/availability/{date}")
def get_day_availability(date: str):
    """Return available slots for a single date."""
    try:
        d = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")

    if d.weekday() not in WEEKDAYS:
        return {"date": date, "slots": [], "message": "Weekends are not available"}
    if d.date() < _today():
        return {"date": date, "slots": [], "message": "Past dates are not available"}

    with _get_db() as db:
        rows = db.execute(
            _sql("SELECT preferred_time FROM bookings WHERE preferred_date = ? AND status != 'cancelled'"),
            (date,),
        ).fetchall()

    taken = {row["preferred_time"] for row in rows}
    return {"date": date, "slots": sorted(VALID_TIMES - taken)}


def list_bookings():
    """Return all bookings, newest first for admin."""
    with _get_db() as db:
        rows = db.execute(
            "SELECT * FROM bookings ORDER BY preferred_date DESC, preferred_time DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def update_status(booking_id: int, body: StatusUpdate):
    """Confirm or cancel a booking."""
    with _get_db() as db:
        existing = db.execute(
            _sql("SELECT id FROM bookings WHERE id = ?"),
            (booking_id,),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Booking not found")
        db.execute(
            _sql("UPDATE bookings SET status = ? WHERE id = ?"),
            (body.status, booking_id),
        )
    return {"id": booking_id, "status": body.status}
