"""SQLite connection, initialization, and demo data seeding."""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

from schema import MOMENT_GROUP_EXERCISE, SCHEMA_STATEMENTS

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = Path(os.environ.get("GCA_DB_PATH", BASE_DIR / "graduate_assessment.db"))


def utc_now() -> str:
    """Return a compact ISO timestamp for persisted records."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_database(
    db_path: str | Path | None = None,
    *,
    seed_demo: bool = True,
) -> None:
    """Create tables if needed and optionally add demo data once."""
    with get_connection(db_path) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        if seed_demo:
            seed_demo_data(conn)
        conn.commit()


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def seed_demo_data(conn: sqlite3.Connection) -> None:
    """Insert a small demo setup only when the database is empty."""
    if _count_rows(conn, "assessment_nights") or _count_rows(conn, "candidates"):
        return

    now = utc_now()
    today = date.today().isoformat()

    night_cursor = conn.execute(
        """
        INSERT INTO assessment_nights (name, date, location, active, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Demo Graduate Assessment Night", today, "Main office", 1, now),
    )
    demo_night_id = int(night_cursor.lastrowid)

    conn.execute(
        """
        INSERT INTO assessment_nights (name, date, location, active, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Archived Example Night", today, "Remote", 0, now),
    )

    demo_candidates = [
        ("Alex", "Morgan", "alex.morgan@example.com", "Demo candidate"),
        ("Sam", "Patel", "sam.patel@example.com", "Demo candidate"),
        ("Jordan", "Lee", "jordan.lee@example.com", "Demo candidate"),
    ]

    candidate_ids: list[int] = []
    for first_name, last_name, email, notes in demo_candidates:
        cursor = conn.execute(
            """
            INSERT INTO candidates
                (first_name, last_name, email, notes, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (first_name, last_name, email, notes, 1, now),
        )
        candidate_ids.append(int(cursor.lastrowid))

    for candidate_id in candidate_ids:
        conn.execute(
            """
            INSERT OR IGNORE INTO assessment_night_candidates
                (assessment_night_id, candidate_id)
            VALUES (?, ?)
            """,
            (demo_night_id, candidate_id),
        )

    conn.execute(
        """
        INSERT INTO evaluations (
            assessment_night_id,
            candidate_id,
            moment,
            assessor_name,
            leadership_collaboration,
            analytical_capabilities,
            individual_performance,
            additional_comments,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            demo_night_id,
            candidate_ids[0],
            MOMENT_GROUP_EXERCISE,
            "Demo Assessor",
            "Contributed early, invited quieter participants into the discussion, and helped the group stay aligned on the task.",
            "Structured the case into clear workstreams and made sensible assumptions when information was incomplete.",
            "Communicated recommendations clearly and stayed composed when challenged.",
            "Good example record for testing the results view and Excel export.",
            now,
        ),
    )
