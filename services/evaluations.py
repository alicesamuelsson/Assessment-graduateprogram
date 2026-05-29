"""Evaluation validation, persistence, and reporting queries."""

from __future__ import annotations

import sqlite3

from db import utc_now
from schema import MOMENT_GROUP_EXERCISE, MOMENT_INDIVIDUAL_INTERVIEW, MOMENTS


def candidate_belongs_to_night(
    conn: sqlite3.Connection,
    *,
    assessment_night_id: int,
    candidate_id: int,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM assessment_night_candidates
        WHERE assessment_night_id = ? AND candidate_id = ?
        """,
        (assessment_night_id, candidate_id),
    ).fetchone()
    return row is not None


def validate_evaluation(
    conn: sqlite3.Connection,
    *,
    assessment_night_id: int,
    candidate_id: int,
    moment: str,
    leadership_collaboration: str,
    analytical_capabilities: str,
    individual_performance: str,
) -> list[str]:
    errors: list[str] = []

    if moment not in MOMENTS:
        errors.append("Assessment moment must be Group Exercise or Individual Interview.")

    if not candidate_belongs_to_night(
        conn,
        assessment_night_id=assessment_night_id,
        candidate_id=candidate_id,
    ):
        errors.append("Candidate is not assigned to the selected assessment night.")

    if not leadership_collaboration.strip():
        errors.append("Leadership and collaboration is required.")
    if not analytical_capabilities.strip():
        errors.append("Analytical capabilities is required.")
    if not individual_performance.strip():
        errors.append("Individual performance within the case is required.")

    return errors


def duplicate_exists(
    conn: sqlite3.Connection,
    *,
    assessment_night_id: int,
    candidate_id: int,
    moment: str,
    assessor_name: str | None,
) -> bool:
    assessor_name = (assessor_name or "").strip()

    if assessor_name:
        row = conn.execute(
            """
            SELECT 1
            FROM evaluations
            WHERE assessment_night_id = ?
                AND candidate_id = ?
                AND moment = ?
                AND lower(trim(coalesce(assessor_name, ''))) = lower(?)
            LIMIT 1
            """,
            (assessment_night_id, candidate_id, moment, assessor_name),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT 1
            FROM evaluations
            WHERE assessment_night_id = ?
                AND candidate_id = ?
                AND moment = ?
                AND trim(coalesce(assessor_name, '')) = ''
            LIMIT 1
            """,
            (assessment_night_id, candidate_id, moment),
        ).fetchone()

    return row is not None


def save_evaluation(
    conn: sqlite3.Connection,
    *,
    assessment_night_id: int,
    candidate_id: int,
    moment: str,
    assessor_name: str | None,
    leadership_collaboration: str,
    analytical_capabilities: str,
    individual_performance: str,
    additional_comments: str | None = None,
) -> int:
    errors = validate_evaluation(
        conn,
        assessment_night_id=assessment_night_id,
        candidate_id=candidate_id,
        moment=moment,
        leadership_collaboration=leadership_collaboration,
        analytical_capabilities=analytical_capabilities,
        individual_performance=individual_performance,
    )
    if errors:
        raise ValueError(" ".join(errors))

    cursor = conn.execute(
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
            assessment_night_id,
            candidate_id,
            moment,
            (assessor_name or "").strip() or None,
            leadership_collaboration.strip(),
            analytical_capabilities.strip(),
            individual_performance.strip(),
            (additional_comments or "").strip() or None,
            utc_now(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_evaluations(
    conn: sqlite3.Connection,
    *,
    assessment_night_id: int | None = None,
    candidate_id: int | None = None,
    moment: str | None = None,
) -> list[dict]:
    conditions: list[str] = []
    params: list[object] = []

    if assessment_night_id is not None:
        conditions.append("e.assessment_night_id = ?")
        params.append(assessment_night_id)
    if candidate_id is not None:
        conditions.append("e.candidate_id = ?")
        params.append(candidate_id)
    if moment:
        conditions.append("e.moment = ?")
        params.append(moment)

    query = """
        SELECT
            e.*,
            n.name AS assessment_night_name,
            n.date AS assessment_night_date,
            c.first_name,
            c.last_name,
            trim(c.first_name || ' ' || c.last_name) AS candidate_name
        FROM evaluations e
        INNER JOIN assessment_nights n
            ON n.id = e.assessment_night_id
        INNER JOIN candidates c
            ON c.id = e.candidate_id
    """

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        ORDER BY
            c.last_name ASC,
            c.first_name ASC,
            CASE e.moment
                WHEN ? THEN 1
                WHEN ? THEN 2
                ELSE 3
            END,
            e.created_at DESC
    """
    params.extend([MOMENT_GROUP_EXERCISE, MOMENT_INDIVIDUAL_INTERVIEW])

    return [dict(row) for row in conn.execute(query, params).fetchall()]


def get_completion_overview(
    conn: sqlite3.Connection,
    *,
    assessment_night_id: int,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            c.id AS candidate_id,
            trim(c.first_name || ' ' || c.last_name) AS candidate_name,
            c.active AS candidate_active,
            COUNT(e.id) AS evaluation_count,
            MAX(CASE WHEN e.moment = ? THEN 1 ELSE 0 END)
                AS has_group_exercise_feedback,
            MAX(CASE WHEN e.moment = ? THEN 1 ELSE 0 END)
                AS has_individual_interview_feedback
        FROM assessment_night_candidates anc
        INNER JOIN candidates c
            ON c.id = anc.candidate_id
        LEFT JOIN evaluations e
            ON e.assessment_night_id = anc.assessment_night_id
            AND e.candidate_id = anc.candidate_id
        WHERE anc.assessment_night_id = ?
        GROUP BY c.id, c.first_name, c.last_name, c.active
        ORDER BY c.last_name ASC, c.first_name ASC
        """,
        (MOMENT_GROUP_EXERCISE, MOMENT_INDIVIDUAL_INTERVIEW, assessment_night_id),
    ).fetchall()
    return [dict(row) for row in rows]
