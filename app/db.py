"""
SQLite database layer.

Manages the relational schema, seed data, and query helpers for the four
tables that back the agent's transactional tools:

  members             — gym member records keyed by WhatsApp phone number
  class_schedule      — upcoming group class instances
  trial_bookings      — prospect trial-class reservations
  class_registrations — member registrations for scheduled classes
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from app.config import DEMO_MEMBER_PHONE

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------
DB: Path = Path(__file__).resolve().parent.parent / "data" / "gym.db"


def get_conn() -> sqlite3.Connection:
    """Return a new SQLite connection with row-factory enabled."""
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables (if not exist) and insert seed data for demo purposes."""
    conn = get_conn()
    cur = conn.cursor()

    # -- members --------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            phone   TEXT    UNIQUE NOT NULL,
            name    TEXT    NOT NULL,
            plan    TEXT    NOT NULL,
            expiry  TEXT    NOT NULL
        )
    """)

    # -- class_schedule -------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS class_schedule (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            class_type  TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            time        TEXT    NOT NULL,
            instructor  TEXT    NOT NULL,
            capacity    INTEGER NOT NULL DEFAULT 20
        )
    """)

    # -- trial_bookings -------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trial_bookings (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            phone   TEXT    NOT NULL,
            name    TEXT,
            date    TEXT    NOT NULL,
            time    TEXT    NOT NULL
        )
    """)

    # -- class_registrations --------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS class_registrations (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            phone     TEXT    NOT NULL,
            class_id  INTEGER NOT NULL,
            FOREIGN KEY (class_id) REFERENCES class_schedule(id)
        )
    """)

    # -- seed data (idempotent — only if tables are empty) --------------------
    if cur.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0:
        _seed_data(cur)

    conn.commit()
    conn.close()


def _seed_data(cur: sqlite3.Cursor) -> None:
    """Insert demo member and upcoming classes for the next 7 days."""
    today = date.today()

    # Demo member — phone from .env so you can test with your own number
    cur.execute(
        "INSERT INTO members (phone, name, plan, expiry) VALUES (?, ?, ?, ?)",
        (DEMO_MEMBER_PHONE, "Alex Rivera", "Premium Monthly",
         (today + timedelta(days=365)).isoformat()),
    )

    # Upcoming classes
    _classes = [
        ("Yoga",     today + timedelta(days=1),  "08:00", "Marcus Williams", 25),
        ("HIIT",     today + timedelta(days=2),  "06:00", "Marcus Williams", 20),
        ("Spinning", today + timedelta(days=3),  "07:00", "Sarah Chen",      18),
        ("Pilates",  today + timedelta(days=1),  "10:00", "Sarah Chen",      20),
        ("Yoga",     today + timedelta(days=3),  "08:00", "Marcus Williams", 25),
        ("HIIT",     today + timedelta(days=4),  "17:30", "Marcus Williams", 20),
        ("Zumba",    today + timedelta(days=5),  "19:00", "Sarah Chen",      30),
    ]
    cur.executemany(
        "INSERT INTO class_schedule (class_type, date, time, instructor, capacity) "
        "VALUES (?, ?, ?, ?, ?)",
        _classes,
    )


# ---------------------------------------------------------------------------
# Query helpers — used by the tool layer (tools.py)
# ---------------------------------------------------------------------------

def get_member(phone: str) -> Optional[dict[str, Any]]:
    """Look up a member by WhatsApp phone number."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id, phone, name, plan, expiry FROM members WHERE phone = ?",
        (phone,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_next_class(class_type: str) -> list[dict[str, Any]]:
    """Return upcoming instances of *class_type* (today or later), soonest first."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, class_type, date, time, instructor, capacity "
        "FROM class_schedule "
        "WHERE class_type = ? AND date >= ? "
        "ORDER BY date ASC, time ASC "
        "LIMIT 3",
        (class_type, date.today().isoformat()),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_trial_booking(phone: str, date_val: str, time_val: str, name: str = "") -> int:
    """Create a trial booking and return the new row ID."""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO trial_bookings (phone, name, date, time) VALUES (?, ?, ?, ?)",
        (phone, name, date_val, time_val),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def insert_class_registration(phone: str, class_id: int) -> int:
    """Register a member for a class and return the new row ID."""
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO class_registrations (phone, class_id) VALUES (?, ?)",
        (phone, class_id),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id
