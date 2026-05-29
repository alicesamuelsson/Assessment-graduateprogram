"""Admin service functions for assessment nights, candidates, and assignments."""

from __future__ import annotations

import sqlite3
from typing import Iterable

from db import utc_now


def _as_bool_int(value: bool) -> int:
    return 1 if value else 0


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def candidate_full_name(candidate: dict | sqlite3.Row) -> str:
    return f"{candidate['first_name']} {candidate['last_name']}".strip()


def list_assessment_nights(
    conn: sqlite3.Connection,
    *,
    active_only: bool = False,
) -> list[dict]:
    query = "SELECT * FROM assessment_nights"
    params: list[object] = []
    if active_only:
        query += " WHERE active = ?"
        params.append(1)
    query += " ORDER BY active DESC, date DESC, created_at DESC, name ASC"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_assessment_night(conn: sqlite3.Connection, night_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM assessment_nights WHERE id = ?",
        (night_id,),
    ).fetchone()
    return _row_to_dict(row)


def create_assessment_night(
    conn: sqlite3.Connection,
    *,
    name: str,
    date: str | None = None,
    location: str | None = None,
    active: bool = True,
) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Assessment night name is required.")

    cursor = conn.execute(
        """
        INSERT INTO assessment_nights (name, date, location, active, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            name,
            (date or "").strip() or None,
            (location or "").strip() or None,
            _as_bool_int(active),
            utc_now(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_assessment_night(
    conn: sqlite3.Connection,
    *,
    night_id: int,
    name: str,
    date: str | None = None,
    location: str | None = None,
    active: bool = True,
) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Assessment night name is required.")

    conn.execute(
        """
        UPDATE assessment_nights
        SET name = ?, date = ?, location = ?, active = ?
        WHERE id = ?
        """,
        (
            name,
            (date or "").strip() or None,
            (location or "").strip() or None,
            _as_bool_int(active),
            night_id,
        ),
    )
    conn.commit()


def list_candidates(
    conn: sqlite3.Connection,
    *,
    active_only: bool = False,
    search: str | None = None,
) -> list[dict]:
    query = "SELECT * FROM candidates"
    conditions: list[str] = []
    params: list[object] = []

    if active_only:
        conditions.append("active = ?")
        params.append(1)

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        conditions.append(
            """
            (
                lower(first_name) LIKE ?
                OR lower(last_name) LIKE ?
                OR lower(coalesce(email, '')) LIKE ?
            )
            """
        )
        params.extend([term, term, term])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY active DESC, last_name ASC, first_name ASC"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_candidate(conn: sqlite3.Connection, candidate_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    return _row_to_dict(row)


def create_candidate(
    conn: sqlite3.Connection,
    *,
    first_name: str,
    last_name: str,
    email: str | None = None,
    notes: str | None = None,
    active: bool = True,
) -> int:
    first_name = first_name.strip()
    last_name = last_name.strip()
    if not first_name or not last_name:
        raise ValueError("Candidate first name and last name are required.")

    cursor = conn.execute(
        """
        INSERT INTO candidates
            (first_name, last_name, email, notes, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            first_name,
            last_name,
            (email or "").strip() or None,
            (notes or "").strip() or None,
            _as_bool_int(active),
            utc_now(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_candidate(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    first_name: str,
    last_name: str,
    email: str | None = None,
    notes: str | None = None,
    active: bool = True,
) -> None:
    first_name = first_name.strip()
    last_name = last_name.strip()
    if not first_name or not last_name:
        raise ValueError("Candidate first name and last name are required.")

    conn.execute(
        """
        UPDATE candidates
        SET first_name = ?,
            last_name = ?,
            email = ?,
            notes = ?,
            active = ?
        WHERE id = ?
        """,
        (
            first_name,
            last_name,
            (email or "").strip() or None,
            (notes or "").strip() or None,
            _as_bool_int(active),
            candidate_id,
        ),
    )
    conn.commit()


def list_candidates_for_night(
    conn: sqlite3.Connection,
    night_id: int,
    *,
    active_only: bool = False,
) -> list[dict]:
    query = """
        SELECT c.*
        FROM candidates c
        INNER JOIN assessment_night_candidates anc
            ON anc.candidate_id = c.id
        WHERE anc.assessment_night_id = ?
    """
    params: list[object] = [night_id]
    if active_only:
        query += " AND c.active = ?"
        params.append(1)
    query += " ORDER BY c.active DESC, c.last_name ASC, c.first_name ASC"
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_candidate_assessment_night_ids(
    conn: sqlite3.Connection,
    candidate_id: int,
) -> list[int]:
    rows = conn.execute(
        """
        SELECT assessment_night_id
        FROM assessment_night_candidates
        WHERE candidate_id = ?
        ORDER BY assessment_night_id
        """,
        (candidate_id,),
    ).fetchall()
    return [int(row["assessment_night_id"]) for row in rows]


def assign_candidate_to_night(
    conn: sqlite3.Connection,
    *,
    assessment_night_id: int,
    candidate_id: int,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO assessment_night_candidates
            (assessment_night_id, candidate_id)
        VALUES (?, ?)
        """,
        (assessment_night_id, candidate_id),
    )
    conn.commit()


def set_candidate_assessment_nights(
    conn: sqlite3.Connection,
    *,
    candidate_id: int,
    assessment_night_ids: Iterable[int],
) -> None:
    selected_ids = {int(night_id) for night_id in assessment_night_ids}
    existing_ids = set(get_candidate_assessment_night_ids(conn, candidate_id))

    for night_id in selected_ids - existing_ids:
        conn.execute(
            """
            INSERT OR IGNORE INTO assessment_night_candidates
                (assessment_night_id, candidate_id)
            VALUES (?, ?)
            """,
            (night_id, candidate_id),
        )

    for night_id in existing_ids - selected_ids:
        conn.execute(
            """
            DELETE FROM assessment_night_candidates
            WHERE assessment_night_id = ? AND candidate_id = ?
            """,
            (night_id, candidate_id),
        )

    conn.commit()
