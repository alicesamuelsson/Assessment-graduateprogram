from __future__ import annotations

from io import BytesIO

import openpyxl
import pytest

from db import get_connection, initialize_database
from schema import MOMENT_GROUP_EXERCISE, MOMENT_INDIVIDUAL_INTERVIEW
from services import admin, evaluations, export


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "test_assessment.db"
    initialize_database(db_path, seed_demo=False)
    connection = get_connection(db_path)
    try:
        yield connection
    finally:
        connection.close()


def test_database_initialization_creates_tables(conn):
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    assert "assessment_nights" in tables
    assert "candidates" in tables
    assert "assessment_night_candidates" in tables
    assert "evaluations" in tables


def test_create_candidate_assign_and_save_evaluation(conn):
    night_id = admin.create_assessment_night(
        conn,
        name="Assessment Night A",
        date="2026-06-01",
        location="Office",
    )
    candidate_id = admin.create_candidate(
        conn,
        first_name="Taylor",
        last_name="Nguyen",
        email="taylor@example.com",
    )
    admin.assign_candidate_to_night(
        conn,
        assessment_night_id=night_id,
        candidate_id=candidate_id,
    )

    evaluation_id = evaluations.save_evaluation(
        conn,
        assessment_night_id=night_id,
        candidate_id=candidate_id,
        moment=MOMENT_GROUP_EXERCISE,
        assessor_name="Assessor One",
        leadership_collaboration="Helped the group align on priorities.",
        analytical_capabilities="Structured the case into clear hypotheses.",
        individual_performance="Presented clearly and responded well.",
        additional_comments="Strong discussion presence.",
    )

    rows = evaluations.list_evaluations(conn, assessment_night_id=night_id)
    overview = evaluations.get_completion_overview(
        conn,
        assessment_night_id=night_id,
    )

    assert evaluation_id > 0
    assert len(rows) == 1
    assert rows[0]["candidate_name"] == "Taylor Nguyen"
    assert overview[0]["evaluation_count"] == 1
    assert overview[0]["has_group_exercise_feedback"] == 1
    assert overview[0]["has_individual_interview_feedback"] == 0


def test_evaluation_requires_valid_assignment_and_moment(conn):
    night_id = admin.create_assessment_night(conn, name="Assessment Night A")
    candidate_id = admin.create_candidate(
        conn,
        first_name="Riley",
        last_name="Chen",
    )

    with pytest.raises(ValueError):
        evaluations.save_evaluation(
            conn,
            assessment_night_id=night_id,
            candidate_id=candidate_id,
            moment="Presentation",
            assessor_name=None,
            leadership_collaboration="Observed",
            analytical_capabilities="Observed",
            individual_performance="Observed",
        )


def test_excel_export_contains_required_sheets(conn):
    night_id = admin.create_assessment_night(
        conn,
        name="Assessment Night Export",
        date="2026-06-02",
    )
    candidate_id = admin.create_candidate(
        conn,
        first_name="Morgan",
        last_name="Diaz",
    )
    admin.assign_candidate_to_night(
        conn,
        assessment_night_id=night_id,
        candidate_id=candidate_id,
    )
    evaluations.save_evaluation(
        conn,
        assessment_night_id=night_id,
        candidate_id=candidate_id,
        moment=MOMENT_INDIVIDUAL_INTERVIEW,
        assessor_name="Assessor Two",
        leadership_collaboration="Listened carefully and built on feedback.",
        analytical_capabilities="Used facts and assumptions effectively.",
        individual_performance="Explained reasoning with confidence.",
        additional_comments="Good fit for the role.",
    )

    workbook_bytes = export.build_excel_export(conn, night_id)
    workbook = openpyxl.load_workbook(BytesIO(workbook_bytes))

    assert workbook.sheetnames == [
        "Overview",
        "Raw Evaluations",
        "By Candidate",
        "Comments Summary",
    ]
    assert workbook["Overview"]["A1"].value == "Candidate name"
    assert workbook["Raw Evaluations"]["D1"].value == "Assessment moment"
