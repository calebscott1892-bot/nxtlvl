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
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_active_booking_slot
ON bookings (preferred_date, preferred_time)
WHERE status != 'cancelled';

