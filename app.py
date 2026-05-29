from __future__ import annotations

import pandas as pd
import streamlit as st

from db import DEFAULT_DB_PATH, get_connection, initialize_database
from schema import MOMENT_GROUP_EXERCISE, MOMENT_INDIVIDUAL_INTERVIEW, MOMENTS
from services import admin, evaluations, export


st.set_page_config(
    page_title="Graduate Candidate Assessment App",
    page_icon="GC",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }
    div.stButton > button,
    div.stDownloadButton > button {
        border-radius: 6px;
        min-height: 2.4rem;
    }
    .muted {
        color: #667085;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def connect():
    initialize_database()
    return get_connection()


def night_label(night: dict) -> str:
    parts = [night["name"]]
    if night.get("date"):
        parts.append(night["date"])
    if night.get("location"):
        parts.append(night["location"])
    if not night.get("active"):
        parts.append("inactive")
    return " | ".join(parts)


def candidate_label(candidate: dict) -> str:
    label = admin.candidate_full_name(candidate)
    if candidate.get("email"):
        label += f" | {candidate['email']}"
    if not candidate.get("active"):
        label += " | inactive"
    return label


def clear_evaluation_keys(night_id: int, candidate_id: int, moment: str) -> None:
    suffix = f"{night_id}_{candidate_id}_{moment.replace(' ', '_')}"
    for prefix in [
        "assessor_name",
        "leadership",
        "analytical",
        "individual",
        "comments",
    ]:
        st.session_state.pop(f"{prefix}_{suffix}", None)
    st.session_state.pop(f"pending_duplicate_{suffix}", None)


def reset_assessor_flow() -> None:
    st.session_state.assessor_step = "night"
    st.session_state.selected_night_id = None
    st.session_state.selected_candidate_id = None
    st.session_state.selected_moment = None


def ensure_assessor_state() -> None:
    st.session_state.setdefault("assessor_step", "night")
    st.session_state.setdefault("selected_night_id", None)
    st.session_state.setdefault("selected_candidate_id", None)
    st.session_state.setdefault("selected_moment", None)


def save_evaluation_payload(conn, payload: dict) -> None:
    evaluations.save_evaluation(conn, **payload)
    clear_evaluation_keys(
        payload["assessment_night_id"],
        payload["candidate_id"],
        payload["moment"],
    )
    st.session_state.last_saved_evaluation = payload
    st.session_state.assessor_step = "saved"
    st.rerun()


def render_assessor_view(conn) -> None:
    ensure_assessor_state()

    st.title("Graduate Candidate Assessment App")
    st.write(
        "Capture structured qualitative observations during assessment nights. "
        "Choose an assessment night, candidate, and moment, then submit written feedback."
    )

    if st.session_state.assessor_step == "night":
        render_assessor_night_step(conn)
    elif st.session_state.assessor_step == "candidate":
        render_assessor_candidate_step(conn)
    elif st.session_state.assessor_step == "moment":
        render_assessor_moment_step(conn)
    elif st.session_state.assessor_step == "evaluation":
        render_assessor_evaluation_step(conn)
    elif st.session_state.assessor_step == "saved":
        render_assessor_saved_step(conn)
    else:
        reset_assessor_flow()
        st.rerun()


def render_assessor_night_step(conn) -> None:
    st.header("Select assessment night")
    active_nights = admin.list_assessment_nights(conn, active_only=True)

    if not active_nights:
        st.info(
            "No active assessment nights are available yet. An admin can create "
            "one in Admin View."
        )
        return

    night_by_id = {night["id"]: night for night in active_nights}
    selected_night_id = st.selectbox(
        "Assessment night",
        options=list(night_by_id),
        format_func=lambda night_id: night_label(night_by_id[night_id]),
    )

    if st.button("Continue", type="primary"):
        st.session_state.selected_night_id = selected_night_id
        st.session_state.assessor_step = "candidate"
        st.rerun()


def render_assessor_candidate_step(conn) -> None:
    night = admin.get_assessment_night(conn, st.session_state.selected_night_id)
    if not night or not night.get("active"):
        st.warning("The selected assessment night is no longer active.")
        reset_assessor_flow()
        st.rerun()

    st.header("Select candidate")
    st.caption(night_label(night))

    candidates = admin.list_candidates_for_night(
        conn,
        st.session_state.selected_night_id,
        active_only=True,
    )

    if not candidates:
        st.info(
            "No active candidates are assigned to this assessment night yet. "
            "An admin can add and assign candidates in Admin View."
        )
        if st.button("Back to assessment night selection"):
            reset_assessor_flow()
            st.rerun()
        return

    candidate_by_id = {candidate["id"]: candidate for candidate in candidates}
    selected_candidate_id = st.selectbox(
        "Candidate",
        options=list(candidate_by_id),
        format_func=lambda candidate_id: candidate_label(candidate_by_id[candidate_id]),
    )

    col_back, col_continue = st.columns([1, 3])
    with col_back:
        if st.button("Back"):
            reset_assessor_flow()
            st.rerun()
    with col_continue:
        if st.button("Continue", type="primary"):
            st.session_state.selected_candidate_id = selected_candidate_id
            st.session_state.assessor_step = "moment"
            st.rerun()


def render_assessor_moment_step(conn) -> None:
    night = admin.get_assessment_night(conn, st.session_state.selected_night_id)
    candidate = admin.get_candidate(conn, st.session_state.selected_candidate_id)
    if not night or not candidate:
        reset_assessor_flow()
        st.rerun()

    st.header("Select assessment moment")
    st.caption(f"{night_label(night)} | {admin.candidate_full_name(candidate)}")

    selected_moment = st.radio(
        "Assessment moment",
        options=list(MOMENTS),
        horizontal=True,
    )

    col_back, col_continue = st.columns([1, 3])
    with col_back:
        if st.button("Back to candidates"):
            st.session_state.assessor_step = "candidate"
            st.rerun()
    with col_continue:
        if st.button("Continue", type="primary"):
            st.session_state.selected_moment = selected_moment
            st.session_state.assessor_step = "evaluation"
            st.rerun()


def render_assessor_evaluation_step(conn) -> None:
    night = admin.get_assessment_night(conn, st.session_state.selected_night_id)
    candidate = admin.get_candidate(conn, st.session_state.selected_candidate_id)
    moment = st.session_state.selected_moment

    if not night or not candidate or moment not in MOMENTS:
        reset_assessor_flow()
        st.rerun()

    st.header("Evaluation form")
    st.caption(f"{night_label(night)} | {admin.candidate_full_name(candidate)} | {moment}")

    suffix = f"{night['id']}_{candidate['id']}_{moment.replace(' ', '_')}"
    pending_key = f"pending_duplicate_{suffix}"
    pending_payload = st.session_state.get(pending_key)

    if pending_payload:
        st.warning(
            "An evaluation already exists for this assessor, candidate, and "
            "assessment moment. Save anyway only if this is intentional."
        )
        col_save, col_edit = st.columns([1, 3])
        with col_save:
            if st.button("Save anyway", type="primary"):
                save_evaluation_payload(conn, pending_payload)
        with col_edit:
            if st.button("Edit first"):
                st.session_state.pop(pending_key, None)
                st.rerun()

    with st.form(f"evaluation_form_{suffix}", clear_on_submit=False):
        assessor_name = st.text_input(
            "Assessor name (optional)",
            key=f"assessor_name_{suffix}",
            help="Useful while there is no login system. Leave blank if not needed.",
        )
        leadership = st.text_area(
            "Leadership and collaboration",
            key=f"leadership_{suffix}",
            height=150,
            help=(
                "Contributions to the group, listening, collaboration, constructive "
                "initiative, and helping move the discussion forward."
            ),
        )
        analytical = st.text_area(
            "Analytical capabilities",
            key=f"analytical_{suffix}",
            height=150,
            help=(
                "Problem structuring, reasoning, ambiguity handling, use of data "
                "or assumptions, and relevant insights."
            ),
        )
        individual = st.text_area(
            "Individual performance within the case",
            key=f"individual_{suffix}",
            height=150,
            help=(
                "Overall contribution, communication clarity, argument quality, "
                "confidence, professionalism, and ability to explain thinking."
            ),
        )
        comments = st.text_area(
            "Additional comments (optional)",
            key=f"comments_{suffix}",
            height=100,
        )

        submitted = st.form_submit_button("Submit evaluation", type="primary")

    if submitted:
        payload = {
            "assessment_night_id": night["id"],
            "candidate_id": candidate["id"],
            "moment": moment,
            "assessor_name": assessor_name,
            "leadership_collaboration": leadership,
            "analytical_capabilities": analytical,
            "individual_performance": individual,
            "additional_comments": comments,
        }
        errors = evaluations.validate_evaluation(
            conn,
            assessment_night_id=payload["assessment_night_id"],
            candidate_id=payload["candidate_id"],
            moment=payload["moment"],
            leadership_collaboration=payload["leadership_collaboration"],
            analytical_capabilities=payload["analytical_capabilities"],
            individual_performance=payload["individual_performance"],
        )
        if errors:
            for error in errors:
                st.error(error)
        elif evaluations.duplicate_exists(
            conn,
            assessment_night_id=night["id"],
            candidate_id=candidate["id"],
            moment=moment,
            assessor_name=assessor_name,
        ):
            st.session_state[pending_key] = payload
            st.rerun()
        else:
            save_evaluation_payload(conn, payload)

    if st.button("Back to moment selection"):
        st.session_state.assessor_step = "moment"
        st.rerun()


def render_assessor_saved_step(conn) -> None:
    saved = st.session_state.get("last_saved_evaluation", {})
    candidate = admin.get_candidate(conn, saved.get("candidate_id"))
    night = admin.get_assessment_night(conn, saved.get("assessment_night_id"))
    moment = saved.get("moment")

    st.success("Evaluation saved.")
    if candidate and night and moment:
        st.write(
            f"Saved for {admin.candidate_full_name(candidate)} | "
            f"{moment} | {night['name']}"
        )

    other_moment = (
        MOMENT_INDIVIDUAL_INTERVIEW
        if moment == MOMENT_GROUP_EXERCISE
        else MOMENT_GROUP_EXERCISE
    )

    col_other, col_candidate, col_night = st.columns(3)
    with col_other:
        if st.button("Evaluate same candidate in the other moment"):
            st.session_state.selected_moment = other_moment
            st.session_state.assessor_step = "evaluation"
            st.rerun()
    with col_candidate:
        if st.button("Evaluate another candidate"):
            st.session_state.assessor_step = "candidate"
            st.rerun()
    with col_night:
        if st.button("Return to assessment night selection"):
            reset_assessor_flow()
            st.rerun()


def render_admin_view(conn) -> None:
    st.title("Admin View")
    st.write(
        "Manage assessment nights, candidates, assignments, submitted observations, "
        "and exports."
    )

    tab_nights, tab_candidates, tab_results = st.tabs(
        ["Assessment nights", "Candidates", "Results and export"]
    )
    with tab_nights:
        render_admin_nights(conn)
    with tab_candidates:
        render_admin_candidates(conn)
    with tab_results:
        render_admin_results(conn)


def render_admin_nights(conn) -> None:
    st.header("Assessment nights")

    with st.expander("Create a new assessment night", expanded=True):
        with st.form("create_night_form"):
            name = st.text_input("Name")
            date_value = st.text_input("Date", placeholder="YYYY-MM-DD")
            location = st.text_input("Location (optional)")
            active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("Create assessment night", type="primary")

        if submitted:
            try:
                admin.create_assessment_night(
                    conn,
                    name=name,
                    date=date_value,
                    location=location,
                    active=active,
                )
                st.success("Assessment night created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    nights = admin.list_assessment_nights(conn)
    if not nights:
        st.info("No assessment nights yet.")
        return

    st.subheader("Existing assessment nights")
    for night in nights:
        with st.expander(night_label(night), expanded=False):
            with st.form(f"edit_night_{night['id']}"):
                edited_name = st.text_input("Name", value=night["name"])
                edited_date = st.text_input("Date", value=night.get("date") or "")
                edited_location = st.text_input(
                    "Location (optional)",
                    value=night.get("location") or "",
                )
                edited_active = st.checkbox("Active", value=bool(night["active"]))
                submitted = st.form_submit_button("Save changes")
            if submitted:
                try:
                    admin.update_assessment_night(
                        conn,
                        night_id=night["id"],
                        name=edited_name,
                        date=edited_date,
                        location=edited_location,
                        active=edited_active,
                    )
                    st.success("Assessment night updated.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def render_admin_candidates(conn) -> None:
    st.header("Candidates")

    nights = admin.list_assessment_nights(conn)
    night_options = {
        f"{night['name']} ({night.get('date') or 'no date'}) [ID {night['id']}]": night[
            "id"
        ]
        for night in nights
    }

    with st.expander("Add a candidate", expanded=True):
        with st.form("create_candidate_form"):
            col_first, col_last = st.columns(2)
            with col_first:
                first_name = st.text_input("First name")
            with col_last:
                last_name = st.text_input("Last name")
            email = st.text_input("Email (optional)")
            notes = st.text_area("Notes (optional)", height=90)
            selected_labels = st.multiselect(
                "Assign to assessment nights",
                options=list(night_options),
            )
            active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("Add candidate", type="primary")

        if submitted:
            try:
                candidate_id = admin.create_candidate(
                    conn,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    notes=notes,
                    active=active,
                )
                admin.set_candidate_assessment_nights(
                    conn,
                    candidate_id=candidate_id,
                    assessment_night_ids=[night_options[label] for label in selected_labels],
                )
                st.success("Candidate added.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.subheader("Existing candidates")
    search = st.text_input("Search candidates", placeholder="Search by name or email")
    candidates = admin.list_candidates(conn, search=search)
    if not candidates:
        st.info("No candidates found.")
        return

    for candidate in candidates:
        existing_ids = set(
            admin.get_candidate_assessment_night_ids(conn, candidate["id"])
        )
        default_labels = [
            label for label, night_id in night_options.items() if night_id in existing_ids
        ]

        with st.expander(candidate_label(candidate), expanded=False):
            with st.form(f"edit_candidate_{candidate['id']}"):
                col_first, col_last = st.columns(2)
                with col_first:
                    edited_first = st.text_input(
                        "First name",
                        value=candidate["first_name"],
                    )
                with col_last:
                    edited_last = st.text_input(
                        "Last name",
                        value=candidate["last_name"],
                    )
                edited_email = st.text_input(
                    "Email (optional)",
                    value=candidate.get("email") or "",
                )
                edited_notes = st.text_area(
                    "Notes (optional)",
                    value=candidate.get("notes") or "",
                    height=90,
                )
                edited_assignments = st.multiselect(
                    "Assigned assessment nights",
                    options=list(night_options),
                    default=default_labels,
                )
                edited_active = st.checkbox("Active", value=bool(candidate["active"]))
                submitted = st.form_submit_button("Save candidate")

            if submitted:
                try:
                    admin.update_candidate(
                        conn,
                        candidate_id=candidate["id"],
                        first_name=edited_first,
                        last_name=edited_last,
                        email=edited_email,
                        notes=edited_notes,
                        active=edited_active,
                    )
                    admin.set_candidate_assessment_nights(
                        conn,
                        candidate_id=candidate["id"],
                        assessment_night_ids=[
                            night_options[label] for label in edited_assignments
                        ],
                    )
                    st.success("Candidate updated.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))


def render_admin_results(conn) -> None:
    st.header("Results overview")
    nights = admin.list_assessment_nights(conn)
    if not nights:
        st.info("No assessment nights yet.")
        return

    night_by_id = {night["id"]: night for night in nights}
    selected_night_id = st.selectbox(
        "Assessment night",
        options=list(night_by_id),
        format_func=lambda night_id: night_label(night_by_id[night_id]),
        key="results_night_id",
    )
    selected_night = night_by_id[selected_night_id]

    overview_rows = evaluations.get_completion_overview(
        conn,
        assessment_night_id=selected_night_id,
    )
    raw_rows = evaluations.list_evaluations(
        conn,
        assessment_night_id=selected_night_id,
    )

    if not overview_rows:
        st.info(
            "No candidates are assigned to this assessment night yet. Assign "
            "candidates in the Candidates tab before collecting evaluations."
        )
        return

    col_candidates, col_evals, col_group, col_interview = st.columns(4)
    with col_candidates:
        st.metric("Assigned candidates", len(overview_rows))
    with col_evals:
        st.metric("Submitted evaluations", len(raw_rows))
    with col_group:
        st.metric(
            "Group Exercise complete",
            sum(1 for row in overview_rows if row["has_group_exercise_feedback"]),
        )
    with col_interview:
        st.metric(
            "Interview complete",
            sum(
                1
                for row in overview_rows
                if row["has_individual_interview_feedback"]
            ),
        )

    overview_df = pd.DataFrame(
        [
            {
                "Candidate name": row["candidate_name"],
                "Number of evaluations": row["evaluation_count"],
                "Has Group Exercise feedback": "Yes"
                if row["has_group_exercise_feedback"]
                else "No",
                "Has Individual Interview feedback": "Yes"
                if row["has_individual_interview_feedback"]
                else "No",
            }
            for row in overview_rows
        ]
    )
    st.subheader("Completion overview")
    st.dataframe(overview_df, use_container_width=True, hide_index=True)

    st.subheader("Filter observations")
    candidate_filter_options = {"All candidates": None}
    for row in overview_rows:
        candidate_filter_options[row["candidate_name"]] = row["candidate_id"]
    for row in raw_rows:
        candidate_filter_options.setdefault(row["candidate_name"], row["candidate_id"])

    col_candidate, col_moment = st.columns(2)
    with col_candidate:
        selected_candidate_label = st.selectbox(
            "Candidate",
            options=list(candidate_filter_options),
        )
    with col_moment:
        selected_moment = st.selectbox(
            "Assessment moment",
            options=["All moments", *MOMENTS],
        )

    filtered_rows = evaluations.list_evaluations(
        conn,
        assessment_night_id=selected_night_id,
        candidate_id=candidate_filter_options[selected_candidate_label],
        moment=None if selected_moment == "All moments" else selected_moment,
    )

    render_observations(filtered_rows, overview_rows)
    render_export_controls(conn, selected_night, raw_rows)


def render_observations(filtered_rows: list[dict], overview_rows: list[dict]) -> None:
    st.subheader("Submitted observations")

    if not filtered_rows:
        st.info("No evaluations submitted yet.")
        return

    rows_by_candidate: dict[int, list[dict]] = {}
    for row in filtered_rows:
        rows_by_candidate.setdefault(row["candidate_id"], []).append(row)

    ordered_candidates = [
        row
        for row in overview_rows
        if row["candidate_id"] in rows_by_candidate
    ]
    known_ids = {row["candidate_id"] for row in ordered_candidates}
    for candidate_id, rows in rows_by_candidate.items():
        if candidate_id not in known_ids:
            ordered_candidates.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_name": rows[0]["candidate_name"],
                }
            )

    for candidate_row in ordered_candidates:
        candidate_rows = rows_by_candidate[candidate_row["candidate_id"]]
        st.markdown(f"### {candidate_row['candidate_name']}")
        for moment in MOMENTS:
            moment_rows = [row for row in candidate_rows if row["moment"] == moment]
            with st.expander(f"{moment} ({len(moment_rows)})", expanded=True):
                if not moment_rows:
                    st.caption("No evaluations yet")
                    continue
                for row in moment_rows:
                    with st.container(border=True):
                        assessor = row.get("assessor_name") or "Not provided"
                        st.markdown(
                            f"**Assessor:** {assessor}  \n"
                            f"**Submitted:** {row['created_at']}"
                        )
                        st.markdown("**Leadership and collaboration**")
                        st.write(row["leadership_collaboration"])
                        st.markdown("**Analytical capabilities**")
                        st.write(row["analytical_capabilities"])
                        st.markdown("**Individual performance within the case**")
                        st.write(row["individual_performance"])
                        if row.get("additional_comments"):
                            st.markdown("**Additional comments**")
                            st.write(row["additional_comments"])


def render_export_controls(conn, selected_night: dict, raw_rows: list[dict]) -> None:
    st.subheader("Export")
    if not raw_rows:
        st.info("No data is available for export yet.")
        return

    excel_bytes = export.build_excel_export(conn, selected_night["id"])
    st.download_button(
        "Download Excel workbook",
        data=excel_bytes,
        file_name=export.make_export_filename(selected_night),
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

    raw_df = pd.DataFrame(raw_rows)
    st.download_button(
        "Download CSV",
        data=raw_df.to_csv(index=False).encode("utf-8"),
        file_name=export.make_export_filename(selected_night).replace(".xlsx", ".csv"),
        mime="text/csv",
    )


def main() -> None:
    conn = connect()
    st.sidebar.title("Navigation")
    mode = st.sidebar.radio("Mode", ["Assessor View", "Admin View"])
    st.sidebar.caption(f"Local database: {DEFAULT_DB_PATH.name}")

    if mode == "Assessor View":
        render_assessor_view(conn)
    else:
        render_admin_view(conn)


if __name__ == "__main__":
    main()
