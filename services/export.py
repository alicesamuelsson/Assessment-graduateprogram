"""Excel export helpers for qualitative assessment results."""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font

from services import admin, evaluations
from schema import MOMENT_GROUP_EXERCISE, MOMENT_INDIVIDUAL_INTERVIEW, MOMENTS


def _yes_no(value: object) -> str:
    return "Yes" if bool(value) else "No"


def _assessor_label(row: dict) -> str:
    return row.get("assessor_name") or "Assessor not provided"


def _format_observation(row: dict) -> str:
    return "\n".join(
        [
            f"{row['created_at']} | {_assessor_label(row)}",
            f"Leadership and collaboration: {row['leadership_collaboration']}",
            f"Analytical capabilities: {row['analytical_capabilities']}",
            f"Individual performance within the case: {row['individual_performance']}",
        ]
    )


def _format_additional_comment(row: dict) -> str | None:
    comment = row.get("additional_comments")
    if not comment:
        return None
    return f"{row['created_at']} | {_assessor_label(row)}: {comment}"


def build_results_frames(conn, assessment_night_id: int) -> dict[str, pd.DataFrame]:
    night = admin.get_assessment_night(conn, assessment_night_id)
    if not night:
        raise ValueError("Assessment night not found.")

    overview_rows = evaluations.get_completion_overview(
        conn,
        assessment_night_id=assessment_night_id,
    )
    raw_rows = evaluations.list_evaluations(
        conn,
        assessment_night_id=assessment_night_id,
    )

    overview_df = pd.DataFrame(
        [
            {
                "Candidate name": row["candidate_name"],
                "Number of evaluations": row["evaluation_count"],
                "Has Group Exercise feedback": _yes_no(
                    row["has_group_exercise_feedback"]
                ),
                "Has Individual Interview feedback": _yes_no(
                    row["has_individual_interview_feedback"]
                ),
            }
            for row in overview_rows
        ],
        columns=[
            "Candidate name",
            "Number of evaluations",
            "Has Group Exercise feedback",
            "Has Individual Interview feedback",
        ],
    )

    raw_df = pd.DataFrame(
        [
            {
                "Timestamp": row["created_at"],
                "Assessment night": row["assessment_night_name"],
                "Candidate": row["candidate_name"],
                "Assessment moment": row["moment"],
                "Assessor name": row.get("assessor_name") or "",
                "Leadership and collaboration": row["leadership_collaboration"],
                "Analytical capabilities": row["analytical_capabilities"],
                "Individual performance within the case": row[
                    "individual_performance"
                ],
                "Additional comments": row.get("additional_comments") or "",
            }
            for row in raw_rows
        ],
        columns=[
            "Timestamp",
            "Assessment night",
            "Candidate",
            "Assessment moment",
            "Assessor name",
            "Leadership and collaboration",
            "Analytical capabilities",
            "Individual performance within the case",
            "Additional comments",
        ],
    )

    by_candidate_df = pd.DataFrame(
        [
            {
                "Candidate name": row["candidate_name"],
                "Assessment moment": row["moment"],
                "Assessor name": row.get("assessor_name") or "",
                "Leadership and collaboration": row["leadership_collaboration"],
                "Analytical capabilities": row["analytical_capabilities"],
                "Individual performance within the case": row[
                    "individual_performance"
                ],
                "Additional comments": row.get("additional_comments") or "",
                "Timestamp": row["created_at"],
            }
            for row in raw_rows
        ],
        columns=[
            "Candidate name",
            "Assessment moment",
            "Assessor name",
            "Leadership and collaboration",
            "Analytical capabilities",
            "Individual performance within the case",
            "Additional comments",
            "Timestamp",
        ],
    )

    comments_summary = []
    raw_by_candidate = {}
    for row in raw_rows:
        raw_by_candidate.setdefault(row["candidate_id"], []).append(row)

    for overview_row in overview_rows:
        candidate_rows = raw_by_candidate.get(overview_row["candidate_id"], [])
        group_observations = [
            _format_observation(row)
            for row in candidate_rows
            if row["moment"] == MOMENT_GROUP_EXERCISE
        ]
        interview_observations = [
            _format_observation(row)
            for row in candidate_rows
            if row["moment"] == MOMENT_INDIVIDUAL_INTERVIEW
        ]
        additional_comments = [
            formatted
            for row in candidate_rows
            if (formatted := _format_additional_comment(row))
        ]

        comments_summary.append(
            {
                "Candidate name": overview_row["candidate_name"],
                "Group Exercise observations": "\n\n".join(group_observations)
                or "No evaluations yet",
                "Individual Interview observations": "\n\n".join(
                    interview_observations
                )
                or "No evaluations yet",
                "Additional comments": "\n\n".join(additional_comments),
            }
        )

    comments_summary_df = pd.DataFrame(
        comments_summary,
        columns=[
            "Candidate name",
            "Group Exercise observations",
            "Individual Interview observations",
            "Additional comments",
        ],
    )

    return {
        "Overview": overview_df,
        "Raw Evaluations": raw_df,
        "By Candidate": by_candidate_df,
        "Comments Summary": comments_summary_df,
    }


def build_excel_export(conn, assessment_night_id: int) -> bytes:
    frames = build_results_frames(conn, assessment_night_id)
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, frame in frames.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"

            for cell in worksheet[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(wrap_text=True, vertical="top")

            for column_cells in worksheet.columns:
                column_letter = column_cells[0].column_letter
                max_length = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                worksheet.column_dimensions[column_letter].width = min(
                    max(max_length + 2, 14),
                    60,
                )
                for cell in column_cells[1:]:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")

    output.seek(0)
    return output.getvalue()


def make_export_filename(night: dict) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", night["name"]).strip("_").lower()
    if not slug:
        slug = "assessment_night"
    date_part = (night.get("date") or datetime.utcnow().strftime("%Y%m%d")).replace(
        " ",
        "_",
    )
    return f"assessment_results_{slug}_{date_part}.xlsx"
