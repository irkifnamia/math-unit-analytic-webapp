from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.ui import afj_sidebar_brand, app_brand, blank_state, inject_theme, page_header
from services.supabase_store import (
    natural_key_column,
    SupabaseStore,
)


SPM_GRADE_ORDER = ["A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G"]
PSPM_GRADE_ORDER = ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "F"]
GRADE_ORDER = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "E", "F", "G"]
RESULT_COLUMNS = [
    "SPM_ADDMATH",
    "SPM_MATH",
    "PSPM_DM015",
    "PSPM_DM025",
    "AMAT_C1C2",
    "AMAT_C5",
    "AMAT_C8",
    "AMAT_C9C10",
    "PSPM_SEM1",
    "PSPM_SEM2",
]
APP_USERS_TABLE = "app_users"
APP_USERS_COLUMNS = [
    "id",
    "created_at",
    "updated_at",
    "ic_number",
    "full_name",
    "role",
    "pensyarah",
    "is_active",
]
STUDENT_DETAIL_COLUMNS = ["NAMA PELAJAR", "NO MATRIK", "KELAS", "JURUSAN", "SISTEM"]
DIAGNOSTIC_COLUMNS = ["AMAT_C1C2", "AMAT_C5", "AMAT_C8", "AMAT_C9C10"]
GRADE_TEST_COLUMNS = ["PSPM_DM015", "PSPM_DM025", "PSPM_SEM1", "PSPM_SEM2"]
PERFORMANCE_COLUMNS = [*GRADE_TEST_COLUMNS, *DIAGNOSTIC_COLUMNS]
SPM_TEST_COLUMNS = ["SPM_MATH", "SPM_ADDMATH"]
UJIAN_OPTIONS = [*SPM_TEST_COLUMNS, *GRADE_TEST_COLUMNS, *DIAGNOSTIC_COLUMNS]
DATASET_OPTIONS = {
    "Students": "students",
    "Lecturers": "lecturers",
    "Programs": "programs",
    "Results": "results",
}
DATASET_SEARCH_COLUMNS = {
    "students": ["NO MATRIK", "NAMA PELAJAR", "KELAS", "SUBJEK", "JURUSAN", "SISTEM"],
    "lecturers": ["KELAS", "PENSYARAH"],
    "programs": ["NO MATRIK", "PROGRAM"],
    "results": ["NO MATRIK", "NAMA PELAJAR", "SPM_MATH", "SPM_ADDMATH"],
}
SPM_CGPA_MAP = {
    "A+": 4.0,
    "A": 3.67,
    "A-": 3.33,
    "B+": 3.0,
    "B": 2.67,
    "C+": 2.33,
    "C": 2.0,
    "D": 1.67,
    "E": 1.33,
    "G": 0.0,
}
PSPM_CGPA_MAP = {
    "A": 4.0,
    "A-": 3.67,
    "B+": 3.33,
    "B": 3.0,
    "B-": 2.67,
    "C+": 2.33,
    "C": 2.0,
    "C-": 1.67,
    "D+": 1.33,
    "F": 0.0,
}


DUMMY_IC_USERS = {
    "901007025883": {
        "full_name": "AIMAN",
        "role": "Admin",
        "PENSYARAH": None,
    },
    "850505105555": {
        "full_name": "Temporary Executive",
        "role": "Executive",
        "PENSYARAH": None,
    },
    "880808085555": {
        "full_name": "Temporary Lecturer",
        "role": "Lecturer",
        "PENSYARAH": "SURIA",
    },
}


st.set_page_config(
    page_title="MATHEMATICS UNIT ANALYTIC",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()


def login_screen(store: SupabaseStore) -> None:
    left, center, right = st.columns([1, 1.2, 1])
    with center:
        app_brand()
        with st.form("login_form"):
            ic_number = st.text_input("IC Number", placeholder="Example: 900101-14-5555")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            user = authenticate_ic_number(ic_number, store)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error("This IC Number is not allowed yet.")
            st.caption("Temporary allowed ICs: 901007025883, 850505105555, 880808085555")


def authenticate_ic_number(ic_number: str, store: SupabaseStore) -> dict | None:
    normalized_ic = normalize_ic_number(ic_number)
    allowed_users = allowed_ic_users(store)
    user = allowed_users.get(normalized_ic)
    if not user:
        return None
    return {
        "id": normalized_ic,
        "ic_number": normalized_ic,
        "email": None,
        **user,
    }


def allowed_ic_users(store: SupabaseStore | None = None) -> dict[str, dict]:
    if store is not None:
        try:
            app_users = load_app_users(store)
            if not app_users.empty and {"ic_number", "full_name", "role"}.issubset(app_users.columns):
                if "is_active" in app_users.columns:
                    app_users = app_users[app_users["is_active"].fillna(True).astype(bool)]
                users: dict[str, dict] = {}
                for _, row in app_users.iterrows():
                    normalized_ic = normalize_ic_number(row.get("ic_number", ""))
                    if not normalized_ic:
                        continue
                    users[normalized_ic] = {
                        "full_name": row.get("full_name") or "Authorized User",
                        "role": row.get("role") or "Lecturer",
                        "PENSYARAH": row.get("pensyarah"),
                    }
                if users:
                    for ic, profile in DUMMY_IC_USERS.items():
                        users.setdefault(ic, profile)
                    return users
        except Exception:
            pass
    configured_users = st.secrets.get("ALLOWED_IC_USERS", None)
    if configured_users:
        return {
            normalize_ic_number(ic): {
                "full_name": profile.get("full_name", "Authorized User"),
                "role": profile.get("role", "Lecturer"),
                "PENSYARAH": profile.get("PENSYARAH"),
            }
            for ic, profile in dict(configured_users).items()
        }
    return DUMMY_IC_USERS


def load_app_users(store: SupabaseStore) -> pd.DataFrame:
    if hasattr(store, "get_app_users"):
        return store.get_app_users()
    try:
        response = store.client.table(APP_USERS_TABLE).select(",".join(APP_USERS_COLUMNS)).execute()
    except Exception as exc:
        if hasattr(store, "last_errors"):
            store.last_errors.append(f"app_users table query failed: {exc}")
        return pd.DataFrame()
    users = pd.DataFrame(response.data or [])
    if users.empty:
        return users
    sort_columns = [column for column in ["role", "full_name"] if column in users.columns]
    if sort_columns:
        users = users.sort_values(sort_columns, na_position="last")
    return users


def save_app_user(store: SupabaseStore, payload: dict, record_id: object | None = None) -> None:
    if hasattr(store, "upsert_app_user"):
        store.upsert_app_user(payload, record_id)
        return
    clean = {
        key: value
        for key, value in payload.items()
        if key in ["ic_number", "full_name", "role", "pensyarah", "is_active"]
    }
    clean["ic_number"] = normalize_ic_number(clean.get("ic_number", ""))
    if not clean.get("ic_number") or not clean.get("full_name") or not clean.get("role"):
        raise ValueError("IC number, user's name, and role are required.")
    if record_id:
        store.client.table(APP_USERS_TABLE).update(clean).eq("id", record_id).execute()
    else:
        store.client.table(APP_USERS_TABLE).upsert(clean, on_conflict="ic_number").execute()


def delete_app_user_records(store: SupabaseStore, record_ids: list[object]) -> int:
    if hasattr(store, "delete_app_users"):
        return store.delete_app_users(record_ids)
    if not record_ids:
        return 0
    store.client.table(APP_USERS_TABLE).delete().in_("id", record_ids).execute()
    return len(record_ids)


def normalize_ic_number(ic_number: str) -> str:
    return "".join(character for character in str(ic_number) if character.isdigit())


def render_user_badge(user: dict) -> None:
    st.markdown(
        f"""
        <div style="
            position: fixed;
            top: 0.55rem;
            right: 1.15rem;
            z-index: 2000;
            background: rgba(255,255,255,0.94);
            border: 1px solid #dde2ee;
            border-radius: 999px;
            padding: 0.35rem 0.75rem;
            box-shadow: 0 8px 22px rgba(20,24,39,0.08);
            color: #141827;
            font-family: Inter, Aptos, 'Segoe UI', Arial, sans-serif;
            font-size: 0.82rem;
            font-weight: 750;">
            {user.get("full_name", "User")} <span style="color:#5f6678;">| {user.get("role", "")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_navigation(
    user: dict,
    store: SupabaseStore,
    base_records: pd.DataFrame,
) -> tuple[str, dict[str, list[str]]]:
    with st.sidebar:
        app_brand()
        st.markdown(
            f"<div class='sidebar-user-badge'>{user['full_name']} | {user['role']}</div>",
            unsafe_allow_html=True,
        )

    all_pages = [
        "DEMOGRAPHY",
        "SPM ANALYSIS",
        "PSPM ANALYSIS",
        "DIAGNOSTIC ANALYSIS",
        "LECTURER PROGRESS",
        "CLASS PROGRESS",
        "PROGRAM PROGRESS",
        "DOWNLOAD",
        "DATA MANAGEMENT",
        "ADMIN",
    ]
    role_pages = {
        "Admin": all_pages,
        "Executive": [page for page in all_pages if page != "ADMIN"],
        "Lecturer": [page for page in all_pages if page not in ["ADMIN", "LECTURER PROGRESS"]],
    }
    page = st.sidebar.radio("Navigation", role_pages[user["role"]])

    st.sidebar.divider()
    st.sidebar.subheader("Global Filters")
    if st.sidebar.button("Refresh Supabase data", use_container_width=True):
        store.refresh_cache()
        st.rerun()
    if st.sidebar.button("Clear filters", use_container_width=True):
        for label in ["Pensyarah", "Kelas", "Subjek", "Sistem", "Program", "Jurusan", "Ujian"]:
            st.session_state[f"global_filter_{label}"] = []
        st.rerun()
    options = store.filter_options_from_records(base_records, user)
    filters: dict[str, list[str]] = {}
    for label in ["Pensyarah", "Kelas", "Subjek", "Sistem", "Program", "Jurusan", "Ujian"]:
        values = UJIAN_OPTIONS if label == "Ujian" else options.get(label, [])
        key = f"global_filter_{label}"
        selected_values = st.session_state.get(key, [])
        st.session_state[key] = [value for value in selected_values if value in values]
        filters[label] = st.sidebar.multiselect(
            label,
            values,
            key=key,
            placeholder=f"All {label}",
        )

    st.sidebar.divider()
    with st.sidebar:
        afj_sidebar_brand()
    if st.sidebar.button("Sign out", use_container_width=True):
        store.sign_out()
        st.session_state.clear()
        st.rerun()
    return page, filters


def demography_dashboard(records: pd.DataFrame, user: dict) -> None:
    page_header(
        "DEMOGRAPHY",
        "Live view of classes, subjects, lecturers, and academic program coverage.",
        user["role"],
    )
    if records.empty:
        blank_state("No records match the selected filters. Use Clear filters or Refresh Supabase data in the sidebar.")
        return

    kpis = st.columns(5)
    kpis[0].metric("Students", f"{records['NO MATRIK'].nunique():,}")
    kpis[1].metric("Kelas", f"{records['KELAS'].nunique():,}")
    kpis[2].metric("Subjek", f"{records['SUBJEK'].nunique():,}")
    kpis[3].metric("Pensyarah", f"{count_people(records['PENSYARAH']):,}")
    kpis[4].metric("Jurusan", f"{records['JURUSAN'].nunique():,}")

    left, right = st.columns(2)
    with left:
        jurusan_counts = records.drop_duplicates("NO MATRIK")["JURUSAN"].value_counts().reset_index()
        jurusan_counts.columns = ["Jurusan", "Students"]
        fig = px.pie(
            jurusan_counts,
            names="Jurusan",
            values="Students",
            hole=0.48,
            title="Distribution by Jurusan",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        class_counts = records.drop_duplicates("NO MATRIK")["KELAS"].value_counts().reset_index()
        class_counts.columns = ["Kelas", "Students"]
        fig = px.bar(
            class_counts,
            x="Students",
            y="Kelas",
            orientation="h",
            title="Distribution by Class",
            color="Students",
            color_continuous_scale="Teal",
        )
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        subject_counts = records["SUBJEK"].value_counts().reset_index()
        subject_counts.columns = ["Subjek", "Records"]
        fig = px.bar(
            subject_counts,
            x="Subjek",
            y="Records",
            title="Distribution by Subject",
            color_discrete_sequence=["#2563eb"],
        )
        fig.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        lecturer_counts = lecturer_count_frame(records)
        fig = px.bar(
            lecturer_counts,
            x="Records",
            y="Pensyarah",
            orientation="h",
            title="Counts by Lecturer",
            color_discrete_sequence=["#0f766e"],
        )
        fig.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Filtered Records")
    render_data_table(
        records[["NO MATRIK", "NAMA PELAJAR", "JURUSAN", "SISTEM", "KELAS", "SUBJEK", "PROGRAM", "PENSYARAH"]],
        "demography_filtered_records",
        "Filtered Demography Records",
    )


def results_dashboard(records: pd.DataFrame, user: dict, filters: dict[str, list[str]]) -> None:
    page_header(
        "SPM ANALYSIS",
        "Analysis for SPM Mathematics and SPM Additional Mathematics achievement.",
        user["role"],
    )
    if records.empty:
        blank_state("No records match the selected filters. Use Clear filters or Refresh Supabase data in the sidebar.")
        return

    selected_spm_columns = selected_ujian_columns(filters, SPM_TEST_COLUMNS)
    if not selected_spm_columns:
        blank_state("The selected Ujian filter does not include SPM_MATH or SPM_ADDMATH.")
        return

    if not all(column in records for column in selected_spm_columns):
        blank_state("SPM analytics need SPM_MATH and SPM_ADDMATH from the Supabase results table.")
        return

    spm_records = records.dropna(subset=selected_spm_columns, how="all")
    if spm_records.empty:
        blank_state("No SPM_MATH or SPM_ADDMATH values match the selected filters.")
        return

    kpis = st.columns(4)
    kpis[0].metric("SPM Math Records", f"{spm_records['SPM_MATH'].notna().sum():,}" if "SPM_MATH" in spm_records else "0")
    kpis[1].metric("SPM Add Math Records", f"{spm_records['SPM_ADDMATH'].notna().sum():,}" if "SPM_ADDMATH" in spm_records else "0")
    kpis[2].metric("ADDMATH A+, A, A-", f"{count_grades(spm_records, 'SPM_ADDMATH', ['A+', 'A', 'A-']):,}")
    kpis[3].metric("ADDMATH E, G", f"{count_grades(spm_records, 'SPM_ADDMATH', ['E', 'G']):,}")

    grade_long = grade_long_frame(spm_records, selected_spm_columns)
    grade_counts = grade_long.value_counts(["RESULT", "GRADE"]).reset_index(name="COUNT")
    if grade_counts.empty:
        blank_state("No valid SPM grades match the selected filters.")
        return

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            grade_counts,
            x="GRADE",
            y="COUNT",
            color="RESULT",
            barmode="group",
            title="SPM Grade Distribution",
            category_orders={"GRADE": GRADE_ORDER},
            color_discrete_sequence=["#1d4ed8", "#0f766e"],
        )
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        addmath_status = addmath_completion_frame(spm_records)
        fig = px.bar(
            addmath_status,
            x="Status",
            y="Count",
            color="Status",
            text="Label",
            title="SPM ADDMATH Participation",
            color_discrete_map={"Taken": "#0f766e", "Not Taken": "#b45309"},
            custom_data=["Percent"],
        )
        fig.update_traces(hovertemplate="%{x}<br>Students: %{y:,}<br>Percentage: %{customdata[0]:.1f}%<extra></extra>")
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    proportions = grade_proportion_frame(grade_counts)
    fig = px.bar(
        proportions,
        x="RESULT",
        y="PERCENT",
        color="GRADE",
        title="Grade Proportion",
        category_orders={"GRADE": GRADE_ORDER},
        color_discrete_sequence=px.colors.qualitative.Safe,
        custom_data=["COUNT"],
    )
    fig.update_traces(
        hovertemplate="%{x}<br>Grade: %{fullData.name}<br>Percentage: %{y:.1f}%<br>Students: %{customdata[0]:,}<extra></extra>"
    )
    fig.update_layout(height=390, yaxis_title="Percent", margin=dict(l=20, r=20, t=55, b=20))
    st.plotly_chart(fig, use_container_width=True)

    render_average_cgpa_comparison(
        spm_records,
        ["SPM_MATH", "SPM_ADDMATH"],
        "Average CGPA Comparison: SPM MATH vs SPM ADDMATH",
    )

    st.subheader("SPM ADDMATH vs SPM MATH Grade Matrix")
    if {"SPM_MATH", "SPM_ADDMATH"}.issubset(selected_spm_columns):
        render_grade_matrix_heatmap(spm_records, "SPM_ADDMATH", "SPM_MATH")
    else:
        blank_state("Select both SPM_MATH and SPM_ADDMATH in Ujian to view the grade matrix.")

    st.subheader("Filtered SPM Records")
    render_data_table(
        spm_records[
            [
                "NO MATRIK",
                "NAMA PELAJAR",
                "KELAS",
                "SUBJEK",
                "PENSYARAH",
                *selected_spm_columns,
            ]
        ],
        "filtered_spm_records",
        "Filtered SPM Records",
    )


def pspm_analysis_page(records: pd.DataFrame, user: dict, filters: dict[str, list[str]]) -> None:
    page_header(
        "PSPM ANALYSIS",
        "Analyse PSPM DM015, DM025, Semester 1, and Semester 2 grade movement.",
        user["role"],
    )
    pspm_columns = selected_ujian_columns(filters, GRADE_TEST_COLUMNS)
    if not pspm_columns:
        blank_state("The selected Ujian filter does not include PSPM assessments.")
        return
    if not any(column in records for column in pspm_columns):
        blank_state("PSPM analytics need PSPM columns from the Supabase results table.")
        return

    pspm_records = records.dropna(subset=[column for column in pspm_columns if column in records], how="all")
    if pspm_records.empty:
        blank_state("No PSPM results match the selected filters.")
        return

    kpis = st.columns(4)
    kpis[0].metric("Average CGPA PSPM DM015", format_average_cgpa(pspm_records, "PSPM_DM015"))
    kpis[1].metric("Average CGPA PSPM DM025", format_average_cgpa(pspm_records, "PSPM_DM025"))
    kpis[2].metric("Average CGPA PSPM SEM 1", format_average_cgpa(pspm_records, "PSPM_SEM1"))
    kpis[3].metric("Average CGPA PSPM SEM 2", format_average_cgpa(pspm_records, "PSPM_SEM2"))

    left, right = st.columns(2)
    with left:
        render_grade_proportion_chart(pspm_records, ["PSPM_DM015", "PSPM_DM025"], "PSPM DM015 vs PSPM DM025 Grade Proportion")
    with right:
        render_grade_proportion_chart(pspm_records, ["PSPM_SEM1", "PSPM_SEM2"], "PSPM SEM1 vs PSPM SEM2 Grade Proportion")

    left, right = st.columns(2)
    with left:
        render_average_cgpa_comparison(
            pspm_records,
            ["PSPM_DM015", "PSPM_DM025"],
            "Average CGPA: PSPM DM015 vs PSPM DM025",
        )
    with right:
        render_average_cgpa_comparison(
            pspm_records,
            ["PSPM_SEM1", "PSPM_SEM2"],
            "Average CGPA: PSPM SEM1 vs PSPM SEM2",
        )

    left, right = st.columns(2)
    with left:
        st.subheader("PSPM DM015 vs PSPM DM025 Matrix")
        render_grade_matrix_heatmap(pspm_records, "PSPM_DM015", "PSPM_DM025")
    with right:
        st.subheader("PSPM SEM1 vs PSPM SEM2 Matrix")
        render_grade_matrix_heatmap(pspm_records, "PSPM_SEM1", "PSPM_SEM2")

    st.subheader("Filtered PSPM Records")
    display_cols = [
        "NO MATRIK",
        "NAMA PELAJAR",
        "KELAS",
        "PENSYARAH",
        "JURUSAN",
        "PROGRAM",
        "SISTEM",
        *pspm_columns,
    ]
    render_data_table(
        pspm_records[[col for col in display_cols if col in pspm_records.columns]],
        "filtered_pspm_records",
        "Filtered PSPM Records",
    )


def diagnostic_dashboard(records: pd.DataFrame, user: dict, filters: dict[str, list[str]]) -> None:
    page_header(
        "DIAGNOSTIC ANALYSIS",
        "Track AMAT diagnostic progress across cohorts, classes, and lecturers.",
        user["role"],
    )
    diagnostic_columns = selected_ujian_columns(filters, DIAGNOSTIC_COLUMNS)
    if not diagnostic_columns:
        blank_state("The selected Ujian filter does not include any AMAT diagnostic tests.")
        return
    diagnostic_long = assessment_long_frame(records, diagnostic_columns)
    if diagnostic_long.empty:
        blank_state("No AMAT diagnostic data match the selected filters.")
        return

    latest_test = diagnostic_columns[-1]
    kpis = st.columns(4)
    kpis[0].metric("Students", f"{diagnostic_long['NO MATRIK'].nunique():,}")
    kpis[1].metric("Average AMAT", f"{diagnostic_long['Score'].mean():.1f}")
    kpis[2].metric("Highest Score", f"{diagnostic_long['Score'].max():.0f}")
    latest_scores = pd.to_numeric(records.get(latest_test, pd.Series(dtype=float)), errors="coerce")
    kpis[3].metric(f"{latest_test} Average", f"{latest_scores.mean():.1f}")

    left, right = st.columns(2)
    with left:
        progress = diagnostic_long.groupby("Test", as_index=False)["Score"].mean()
        fig = px.line(
            progress,
            x="Test",
            y="Score",
            markers=True,
            title="Average Diagnostic Progress",
            category_orders={"Test": diagnostic_columns},
            color_discrete_sequence=["#1d4ed8"],
        )
        fig.update_layout(height=390, yaxis_range=[0, 100], margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        class_progress = diagnostic_long.groupby(["KELAS", "Test"], as_index=False)["Score"].mean()
        fig = px.line(
            class_progress,
            x="Test",
            y="Score",
            color="KELAS",
            markers=True,
            title="All Class Diagnostic Progress",
            category_orders={"Test": diagnostic_columns},
        )
        fig.update_layout(height=390, yaxis_range=[0, 100], margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        fig = px.box(
            diagnostic_long,
            x="Test",
            y="Score",
            points=False,
            title="Score Distribution by Diagnostic",
            category_orders={"Test": diagnostic_columns},
            color_discrete_sequence=["#0f766e"],
        )
        fig.update_layout(height=360, yaxis_range=[0, 100], margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        sistem_heatmap = diagnostic_long.pivot_table(
            index="Test",
            columns="SISTEM",
            values="Score",
            aggfunc="mean",
        ).reindex(index=diagnostic_columns)
        preferred_systems = [system for system in ["SES", "SDS"] if system in sistem_heatmap.columns]
        if preferred_systems:
            sistem_heatmap = sistem_heatmap[preferred_systems]
        fig = px.imshow(
            sistem_heatmap.round(1),
            aspect="auto",
            text_auto=".1f",
            color_continuous_scale="YlGnBu",
            title="Diagnostic Average Heatmap: SES vs SDS",
            zmin=0,
            zmax=100,
        )
        fig.update_layout(height=360, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Diagnostic Records")
    display_cols = [
        "NO MATRIK",
        "NAMA PELAJAR",
        "KELAS",
        "PENSYARAH",
        "JURUSAN",
        "PROGRAM",
        *diagnostic_columns,
    ]
    render_data_table(
        records[[col for col in display_cols if col in records.columns]],
        "diagnostic_records",
        "Diagnostic Records",
    )


def lecturer_progress_page(records: pd.DataFrame, user: dict, filters: dict[str, list[str]]) -> None:
    page_header(
        "LECTURER PROGRESS",
        "Rank lecturer progress by diagnostic, SPM, and PSPM performance across SES, SDS, and overall.",
        user["role"],
    )
    progress_rank_page(records, filters, "PENSYARAH", "Lecturer")


def class_progress_page(records: pd.DataFrame, user: dict, filters: dict[str, list[str]]) -> None:
    page_header(
        "CLASS PROGRESS",
        "Rank class progress by diagnostic, SPM, and PSPM performance across SES, SDS, and overall.",
        user["role"],
    )
    progress_rank_page(records, filters, "KELAS", "Class")


def program_progress_page(records: pd.DataFrame, user: dict, filters: dict[str, list[str]]) -> None:
    page_header(
        "PROGRAM PROGRESS",
        "Rank program progress by diagnostic, SPM, and PSPM performance across SES, SDS, and overall.",
        user["role"],
    )
    records = strip_jurusan_from_program(records)
    progress_rank_page(records, filters, "PROGRAM", "Program")


def comparable_program_label(value: object) -> str:
    return " ".join(str(value).replace("–", "-").replace("—", "-").split()).casefold()


def strip_jurusan_from_program(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty or "PROGRAM" not in records:
        return records
    cleaned = records.copy()
    jurusan_values = {
        comparable_program_label(value)
        for value in cleaned.get("JURUSAN", pd.Series(dtype=str)).dropna().unique().tolist()
        if comparable_program_label(value)
    }
    def invalid_program(value: object) -> bool:
        normalized = comparable_program_label(value)
        return (
            not normalized
            or normalized in jurusan_values
            or "modul" in normalized
            or normalized in {"perakaunan", "sains komputer"}
        )

    cleaned.loc[cleaned["PROGRAM"].apply(invalid_program).fillna(True), "PROGRAM"] = pd.NA
    return cleaned


def progress_rank_page(records: pd.DataFrame, filters: dict[str, list[str]], group_column: str, group_label: str) -> None:
    diagnostic_columns = selected_ujian_columns(filters, DIAGNOSTIC_COLUMNS)
    spm_columns = selected_ujian_columns(filters, SPM_TEST_COLUMNS)
    pspm_columns = selected_ujian_columns(filters, GRADE_TEST_COLUMNS)
    if not [*diagnostic_columns, *spm_columns, *pspm_columns]:
        blank_state("The selected Ujian filter does not include diagnostic, SPM, or PSPM assessments.")
        return

    diagnostic_long = assessment_long_frame(records, diagnostic_columns)
    spm_long = cgpa_long_frame(records, spm_columns, "SPM")
    pspm_long = cgpa_long_frame(records, pspm_columns, "PSPM")
    sections = []
    for column in [*spm_columns, *diagnostic_columns, *pspm_columns]:
        section = progress_section_for_test(column, diagnostic_long, spm_long, pspm_long)
        if section:
            sections.append(section)

    tabs = st.tabs([section[0] for section in sections])
    for tab, (section_label, frame, value_column, metric_label, axis_title) in zip(tabs, sections):
        with tab:
            render_progress_section(
                frame,
                group_column,
                section_label,
                value_column,
                metric_label,
                axis_title,
                records,
            )


def download_page(records: pd.DataFrame, user: dict, store: SupabaseStore) -> None:
    page_header(
        "DOWNLOAD",
        "Choose fields, filter rows, and export the selected dataset.",
        user["role"],
    )
    if records.empty:
        blank_state("No records match the selected filters. Use Clear filters or Refresh Supabase data in the sidebar.")
        return

    available_columns = [column for column in records.columns if column not in ["id", "created_at", "updated_at"]]
    default_columns = [
        column
        for column in [
            "NO MATRIK",
            "NAMA PELAJAR",
            "KELAS",
            "PENSYARAH",
            "JURUSAN",
            "PROGRAM",
            "SUBJEK",
        ]
        if column in available_columns
    ]

    st.subheader("Download Builder")
    selected_columns = st.multiselect(
        "Info fields to download",
        available_columns,
        default=default_columns,
        key="download_selected_columns",
    )

    filtered = records.copy()

    search_text = st.text_input(
        "Search rows",
        placeholder="Search across selected fields after global filters",
        key="download_search_text",
    )
    if search_text.strip():
        search_columns = selected_columns or available_columns
        filtered = search_any_columns(filtered, search_text, search_columns)

    st.metric("Rows ready to download", f"{len(filtered):,}")
    if not selected_columns:
        blank_state("Choose at least one info field to download.")
        return

    export_df = filtered[selected_columns].copy()
    render_data_table(export_df.head(500), "download_preview", "Download Preview")
    render_download_buttons(export_df, "custom_download_filtered_data", "Custom Download Data", user, store)


def admin_page(user: dict, store: SupabaseStore) -> None:
    page_header(
        "ADMIN",
        "Manage user access and monitor application activity.",
        user["role"],
    )
    if user["role"] != "Admin":
        st.error("You do not have permission to access ADMIN.")
        return

    tab_access, tab_activity = st.tabs(["User Access", "App Activity"])
    with tab_access:
        admin_user_access_section(user, store)
    with tab_activity:
        admin_activity_section(store)


def admin_user_access_section(user: dict, store: SupabaseStore) -> None:
    st.subheader("User Access")
    st.caption("Register, update, activate/deactivate, or delete Executive and Lecturer access by IC number.")
    users = load_app_users(store)
    app_user_errors = [error for error in store.last_errors if "app_users" in str(error).lower()]
    if app_user_errors and users.empty:
        st.warning("The app_users table is not available yet. Create it in Supabase before managing access here.")
        with st.expander("Required SQL"):
            st.code(app_users_setup_sql(), language="sql")
        return

    editable_users = users.copy()
    if not editable_users.empty and "role" in editable_users.columns:
        editable_users = editable_users[editable_users["role"].isin(["Executive", "Lecturer"])]

    options = {"New access": None}
    if not editable_users.empty and "id" in editable_users.columns:
        for _, row in editable_users.iterrows():
            label = f"{row.get('ic_number', '')} | {row.get('full_name', '')} | {row.get('role', '')}"
            options[label] = row.get("id")

    selected = st.selectbox("Mode", list(options.keys()), key="admin_access_mode")
    selected_row = None
    if selected != "New access":
        selected_id = str(options[selected])
        selected_row = editable_users.loc[editable_users["id"].astype(str) == selected_id].iloc[0]

    with st.form("admin_access_form"):
        ic_number = st.text_input("IC Number", value=field_value(selected_row, "ic_number"))
        full_name = st.text_input("User's Name", value=field_value(selected_row, "full_name"))
        current_role = field_value(selected_row, "role") or "Executive"
        role = st.selectbox("Role", ["Executive", "Lecturer"], index=["Executive", "Lecturer"].index(current_role) if current_role in ["Executive", "Lecturer"] else 0)
        pensyarah = st.text_input("Pensyarah Name (optional for Lecturer)", value=field_value(selected_row, "pensyarah"))
        is_active = st.checkbox("Active", value=bool(selected_row.get("is_active", True)) if selected_row is not None and "is_active" in selected_row else True)
        submitted = st.form_submit_button("Save access", use_container_width=True)
        if submitted:
            payload = {
                "ic_number": normalize_ic_number(ic_number),
                "full_name": full_name.strip(),
                "role": role,
                "pensyarah": pensyarah.strip(),
                "is_active": is_active,
            }
            record_id = None if selected == "New access" else options[selected]
            save_app_user(store, payload, record_id)
            store.log_edit_history(
                user,
                "USER ACCESS",
                "app_users",
                record_id=record_id,
                details=f"Saved {role} access for {payload['full_name']} ({payload['ic_number']}). Active: {is_active}.",
            )
            st.success("User access saved successfully.")
            st.rerun()

    if editable_users.empty:
        blank_state("No Executive or Lecturer access has been registered yet.")
    else:
        display_columns = ["ic_number", "full_name", "role", "pensyarah", "is_active", "updated_at"]
        access_table = editable_users[[column for column in display_columns if column in editable_users.columns]].rename(
            columns={
                "ic_number": "IC NUMBER",
                "full_name": "USER'S NAME",
                "role": "ROLE",
                "pensyarah": "PENSYARAH",
                "is_active": "ACTIVE",
                "updated_at": "UPDATED AT",
            }
        )
        render_data_table(access_table, "admin_user_access", "Admin User Access")
        delete_options = {
            f"{row.get('ic_number', '')} | {row.get('full_name', '')} | {row.get('role', '')}": row.get("id")
            for _, row in editable_users.iterrows()
            if row.get("id") is not None
        }
        selected_delete = st.multiselect("Select access to delete", list(delete_options.keys()))
        if st.button("Delete selected access", type="secondary", disabled=not selected_delete):
            ids = [delete_options[label] for label in selected_delete]
            deleted = delete_app_user_records(store, ids)
            store.log_edit_history(
                user,
                "DELETE USER ACCESS",
                "app_users",
                details=f"Deleted {deleted} user access record(s): {', '.join(selected_delete[:10])}",
            )
            st.success(f"Deleted {deleted} user access record(s).")
            st.rerun()


def admin_activity_section(store: SupabaseStore) -> None:
    st.subheader("App Activity")
    st.caption("Review create, update, delete, import, and download activity by app users.")
    history = store.get_edit_history()
    if history.empty:
        blank_state("No edit activity has been recorded yet.")
        return

    display = history.copy()
    action_options = sorted(display.get("action", pd.Series(dtype=str)).dropna().unique().tolist())
    dataset_options = sorted(display.get("dataset", pd.Series(dtype=str)).dropna().unique().tolist())
    user_options = sorted(display.get("user_name", pd.Series(dtype=str)).dropna().unique().tolist())
    ic_options = sorted(display.get("user_id", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())

    filters = st.columns(4)
    selected_actions = filters[0].multiselect("Action", action_options, placeholder="All actions")
    selected_datasets = filters[1].multiselect("Dataset", dataset_options, placeholder="All datasets")
    selected_users = filters[2].multiselect("User", user_options, placeholder="All users")
    selected_ics = filters[3].multiselect("IC Number", ic_options, placeholder="All ICs")

    if selected_actions:
        display = display[display["action"].isin(selected_actions)]
    if selected_datasets:
        display = display[display["dataset"].isin(selected_datasets)]
    if selected_users:
        display = display[display["user_name"].isin(selected_users)]
    if selected_ics and "user_id" in display:
        display = display[display["user_id"].astype(str).isin(selected_ics)]

    search_text = st.text_input("Search details", placeholder="Search IC number, action, user, dataset, or details")
    if search_text.strip():
        display = search_any_columns(
            display,
            search_text,
            ["user_id", "user_name", "user_role", "action", "dataset", "record_id", "details"],
        )

    st.metric("History entries", f"{len(display):,}")
    columns = [
        "created_at",
        "user_id",
        "user_name",
        "user_role",
        "action",
        "dataset",
        "record_id",
        "details",
    ]
    history_table = display[[column for column in columns if column in display.columns]].rename(
        columns={
            "created_at": "DATE / TIME",
            "user_id": "IC NUMBER",
            "user_name": "USER",
            "user_role": "ROLE",
            "action": "ACTION",
            "dataset": "DATASET",
            "record_id": "RECORD ID",
            "details": "DETAILS",
        }
    )
    render_data_table(history_table, "admin_app_activity", "Admin App Activity")


def data_management_page(records: pd.DataFrame, user: dict, store: SupabaseStore) -> None:
    page_header(
        "DATA MANAGEMENT",
        "Create, update, delete, import, and validate academic records.",
        user["role"],
    )
    render_data_management_success()
    refs = store.get_reference_data()
    dataset_label = st.selectbox("Dataset", list(DATASET_OPTIONS.keys()), key="dm_dataset")
    dataset_key = DATASET_OPTIONS[dataset_label]
    dataset = dataset_frame(dataset_key, refs)
    writable_columns = store.writable_columns(dataset_key)
    tab_records, tab_form, tab_import, tab_refs = st.tabs(
        ["View or Delete", "Create or Update", "Bulk Import", "Reference Data"]
    )

    with tab_records:
        st.subheader(f"{dataset_label} View or Delete")
        st.caption("Search, review, and delete records from the selected Supabase dataset.")
        record_search = st.text_input(
            "Search records",
            placeholder=dataset_search_placeholder(dataset_key),
            key="delete_record_search",
        )
        record_candidates = search_dataset(dataset, record_search, dataset_key)
        render_data_table(record_candidates, f"{dataset_key}_view_delete", f"{dataset_label} View or Delete")
        delete_options = dataset_option_map(record_candidates, dataset_key)
        selected_labels = st.multiselect("Select records to delete", list(delete_options.keys()))
        selected_ids = [delete_options[label] for label in selected_labels]
        if st.button("Delete selected records", type="secondary", disabled=not selected_ids):
            deleted = store.delete_reference(dataset_key, selected_ids)
            history_logged = store.log_edit_history(
                user,
                "DELETE",
                dataset_key,
                details=f"Deleted {deleted} record(s): {', '.join(str(record_id) for record_id in selected_ids[:20])}",
            )
            set_data_management_success(f"Successfully deleted {deleted} {dataset_label.lower()} record(s).")
            if not history_logged:
                set_data_management_warning("The data was deleted, but edit history was not recorded because the edit_history table is unavailable.")
            st.rerun()

    with tab_form:
        st.subheader(f"Create or Update {dataset_label}")
        update_search = st.text_input(
            "Search record to update",
            placeholder=dataset_search_placeholder(dataset_key),
            key="update_record_search",
        )
        update_candidates = search_dataset(dataset, update_search, dataset_key)
        update_options = {"New record": None, **dataset_option_map(update_candidates, dataset_key)}
        selected = st.selectbox("Mode", list(update_options.keys()))
        selected_row = None
        if selected != "New record":
            selected_id = str(update_options[selected])
            selected_row = dataset.loc[dataset["id"].astype(str) == selected_id].iloc[0]

        with st.form(f"record_form_{dataset_key}"):
            payload = dataset_form_fields(writable_columns, selected_row)

            submitted = st.form_submit_button("Save record", use_container_width=True)
            if submitted:
                record_id = None if selected == "New record" else update_options[selected]
                store.upsert_reference(dataset_key, payload, record_id)
                action = "created" if selected == "New record" else "updated"
                history_logged = store.log_edit_history(
                    user,
                    action.upper(),
                    dataset_key,
                    record_id=record_id,
                    details=f"{action.title()} {dataset_label.lower()} record with fields: {', '.join(payload.keys())}",
                )
                set_data_management_success(f"Successfully {action} {dataset_label.lower()} record.")
                if not history_logged:
                    set_data_management_warning("The data was saved, but edit history was not recorded because the edit_history table is unavailable.")
                st.rerun()

    with tab_import:
        st.subheader(f"Bulk Import and Update {dataset_label}")
        st.caption("Choose the fields to update. Imported rows only update the selected columns; other Supabase columns remain unchanged.")
        default_match_column = natural_key_column(dataset_key)
        match_column = st.selectbox(
            "Match rows by",
            ["id", default_match_column],
            index=1,
            help="Use id for exact row updates, or the natural key to update the first matching row.",
        )
        update_choices = [
            column
            for column in writable_columns
            if not (match_column != "id" and column == match_column)
        ]
        default_update_columns = update_choices[:1] if update_choices else []
        selected_update_columns = st.multiselect(
            "Columns to update",
            update_choices,
            default=default_update_columns,
            help="Only these columns will be changed during bulk import.",
        )
        if not selected_update_columns:
            st.info("Choose at least one column to update before downloading a template or uploading data.")
        else:
            template = selected_upload_template(writable_columns, selected_update_columns, match_column)
            template_csv = template.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV template",
                template_csv,
                f"{dataset_key}_template.csv",
                "text/csv",
            )
            uploaded = st.file_uploader("Upload file", type=["csv", "xlsx", "xls"], key=f"upload_{dataset_key}")
            if uploaded:
                try:
                    if uploaded.name.lower().endswith(".csv"):
                        incoming = pd.read_csv(uploaded)
                    else:
                        incoming = pd.read_excel(uploaded)
                except Exception as exc:
                    st.error(f"Unable to read uploaded file: {exc}")
                    incoming = None

                if incoming is not None:
                    preview, errors = validate_selected_import_frame(
                        incoming,
                        dataset_key,
                        writable_columns,
                        selected_update_columns,
                        match_column,
                    )
                    st.subheader("Preview")
                    render_data_table(preview, f"{dataset_key}_import_preview", f"{dataset_label} Import Preview")
                    if errors:
                        st.error("Please fix the validation errors before saving.")
                        st.write(errors)
                    elif st.button("Save imported data", type="primary", key=f"save_import_{dataset_key}"):
                        if preview.empty:
                            st.error("No rows found in the uploaded file.")
                            return
                        try:
                            saved = store.bulk_upsert_reference(dataset_key, preview, match_column=match_column)
                            if saved <= 0:
                                st.error("No rows were saved. Check that the uploaded file contains valid matching rows.")
                                return
                            history_logged = store.log_edit_history(
                                user,
                                "BULK IMPORT",
                                dataset_key,
                                details=(
                                    f"Saved {saved} {dataset_label.lower()} record(s). "
                                    f"Match column: {match_column}. Updated columns: {', '.join(selected_update_columns)}."
                                ),
                            )
                            success_message = (
                                f"Bulk import successful. {saved} {dataset_label.lower()} record(s) saved. "
                                f"Matching rows were overwritten by {match_column}; blank imported cells cleared existing values."
                            )
                            set_data_management_success(success_message)
                            st.success(success_message)
                            try:
                                st.toast(success_message)
                            except Exception:
                                pass
                            if not history_logged:
                                set_data_management_warning("The import was saved, but edit history was not recorded because the edit_history table is unavailable.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Bulk import failed: {exc}")

    with tab_refs:
        st.subheader(f"{dataset_label} Reference Data")
        render_data_table(dataset, f"{dataset_key}_reference_data", f"{dataset_label} Reference Data")
        st.caption(f"Writable columns: {', '.join(writable_columns)}")


def dataset_frame(dataset_key: str, refs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    df = refs.get(dataset_key, pd.DataFrame()).copy()
    if dataset_key == "results" and "students" in refs and not df.empty:
        students = refs["students"][["NO MATRIK", "NAMA PELAJAR"]].drop_duplicates("NO MATRIK")
        df = df.merge(students, on="NO MATRIK", how="left")
        ordered = [
            "id",
            "created_at",
            "updated_at",
            "NO MATRIK",
            "NAMA PELAJAR",
            *[column for column in RESULT_COLUMNS if column not in ["id", "created_at", "updated_at", "NO MATRIK"]],
        ]
        return df[[column for column in ordered if column in df.columns]]
    return df


def dataset_search_placeholder(dataset_key: str) -> str:
    labels = {
        "students": "Search by NO MATRIK or NAMA PELAJAR",
        "lecturers": "Search by KELAS or PENSYARAH",
        "programs": "Search by NO MATRIK or PROGRAM",
        "results": "Search by NO MATRIK, NAMA PELAJAR, or result value",
    }
    return labels[dataset_key]


def search_dataset(df: pd.DataFrame, query: str, dataset_key: str) -> pd.DataFrame:
    if df.empty or not query:
        return df
    search_text = query.strip().lower()
    if not search_text:
        return df
    columns = [column for column in DATASET_SEARCH_COLUMNS[dataset_key] if column in df.columns]
    if not columns:
        return df
    mask = pd.Series(False, index=df.index)
    for column in columns:
        mask = mask | df[column].fillna("").astype(str).str.lower().str.contains(search_text, regex=False)
    return df[mask]


def set_data_management_success(message: str) -> None:
    st.session_state["data_management_success"] = message
    st.session_state["data_management_success_persist"] = message
    st.session_state["supabase_data_dirty"] = True


def app_users_setup_sql() -> str:
    return """create table if not exists public.app_users (
    id bigint generated by default as identity primary key,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    ic_number text not null unique,
    full_name text not null,
    role text not null check (role in ('Executive', 'Lecturer')),
    pensyarah text,
    is_active boolean not null default true
);

create index if not exists app_users_ic_number_idx
on public.app_users (ic_number);

create index if not exists app_users_role_idx
on public.app_users (role);"""


def set_data_management_warning(message: str) -> None:
    st.session_state["data_management_warning"] = message
    st.session_state["data_management_warning_persist"] = message


def render_data_management_success() -> None:
    message = st.session_state.pop("data_management_success", None) or st.session_state.pop("data_management_success_persist", None)
    warning = st.session_state.pop("data_management_warning", None) or st.session_state.pop("data_management_warning_persist", None)
    if message:
        st.success(message)
        try:
            st.toast(message)
        except Exception:
            pass
    if warning:
        st.warning(warning)


def selected_upload_template(
    writable_columns: list[str],
    update_columns: list[str],
    match_column: str,
) -> pd.DataFrame:
    columns = ["id"] if match_column == "id" else [match_column]
    for column in update_columns:
        if column in writable_columns and column not in columns:
            columns.append(column)
    return pd.DataFrame(columns=columns)


def validate_selected_import_frame(
    raw: pd.DataFrame,
    dataset_key: str,
    writable_columns: list[str],
    update_columns: list[str],
    match_column: str,
) -> tuple[pd.DataFrame, list[str]]:
    template_columns = selected_upload_template(writable_columns, update_columns, match_column).columns.tolist()
    df = raw.copy()
    missing = [column for column in template_columns if column not in df.columns]
    errors = [f"Missing column: {column}" for column in missing]
    if errors:
        return df, errors

    df = df[template_columns].copy()
    for column in df.columns:
        df[column] = df[column].fillna("").astype(str).str.strip()

    allowed_update_columns = [
        column
        for column in update_columns
        if column in writable_columns and column in df.columns and column != match_column
    ]
    if not allowed_update_columns:
        errors.append("Choose at least one valid column to update.")

    for row_number, row in df.iterrows():
        if row.get(match_column, "") == "":
            errors.append(f"Row {row_number + 2}: {match_column} is required")

    return df, errors


def search_any_columns(df: pd.DataFrame, query: str, columns: list[str]) -> pd.DataFrame:
    if df.empty or not query:
        return df
    search_text = query.strip().lower()
    if not search_text:
        return df
    searchable_columns = [column for column in columns if column in df.columns]
    if not searchable_columns:
        return df
    mask = pd.Series(False, index=df.index)
    for column in searchable_columns:
        mask = mask | df[column].fillna("").astype(str).str.lower().str.contains(search_text, regex=False)
    return df[mask]


def dataset_option_map(df: pd.DataFrame, dataset_key: str) -> dict[str, object]:
    options: dict[str, object] = {}
    if df.empty or "id" not in df:
        return options
    label_columns = {
        "students": ["NO MATRIK", "NAMA PELAJAR", "KELAS"],
        "lecturers": ["KELAS", "PENSYARAH"],
        "programs": ["NO MATRIK", "PROGRAM"],
        "results": ["NO MATRIK", "NAMA PELAJAR", "SPM_MATH", "SPM_ADDMATH"],
    }
    for _, row in df.iterrows():
        parts = [field_value(row, column) for column in label_columns[dataset_key]]
        label = " | ".join(part for part in parts if part)
        options[label or str(row["id"])] = row["id"]
    return options


def dataset_form_fields(columns: list[str], selected_row: pd.Series | None) -> dict[str, str]:
    payload: dict[str, str] = {}
    rows = [columns[index : index + 2] for index in range(0, len(columns), 2)]
    for row_columns in rows:
        ui_columns = st.columns(len(row_columns))
        for ui_column, column in zip(ui_columns, row_columns):
            payload[column] = ui_column.text_input(
                column,
                value=field_value(selected_row, column),
            )
    return payload


def safe_key(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in str(value)).strip("_").lower()


def render_table_download_menu(df: pd.DataFrame, file_stem: str, title: str) -> None:
    if df.empty:
        return
    menu_cols = st.columns([10, 1])
    with menu_cols[1]:
        stem = safe_key(file_stem) or "table"
        if hasattr(st, "popover"):
            with st.popover("⋯", help="Download table"):
                st.download_button(
                    "CSV",
                    df.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"{stem}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"{stem}_table_csv",
                )
                st.download_button(
                    "Excel",
                    dataframe_to_excel_bytes(df, title),
                    file_name=f"{stem}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"{stem}_table_xlsx",
                )
        else:
            with st.expander("Download", expanded=False):
                st.download_button("CSV", df.to_csv(index=False).encode("utf-8-sig"), f"{stem}.csv", "text/csv", key=f"{stem}_table_csv")
                st.download_button("Excel", dataframe_to_excel_bytes(df, title), f"{stem}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{stem}_table_xlsx")


def render_data_table(
    df: pd.DataFrame,
    file_stem: str,
    title: str,
    hide_index: bool = True,
    use_container_width: bool = True,
) -> None:
    render_table_download_menu(df, file_stem, title)
    st.dataframe(df, hide_index=hide_index, use_container_width=use_container_width)


def render_download_buttons(
    df: pd.DataFrame,
    file_stem: str,
    title: str,
    user: dict | None = None,
    store: SupabaseStore | None = None,
) -> None:
    export_df = df.copy()
    if export_df.empty:
        return
    st.markdown('<div class="download-strip">', unsafe_allow_html=True)
    col_csv, col_excel, col_pdf_data, spacer = st.columns([1, 1, 1.2, 4.8])
    with col_csv:
        clicked = st.download_button(
            "Download CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{file_stem}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{file_stem}_csv",
        )
        if clicked:
            log_download_activity(user, store, title, "CSV", export_df)
    with col_excel:
        clicked = st.download_button(
            "Download Excel",
            dataframe_to_excel_bytes(export_df, title),
            file_name=f"{file_stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{file_stem}_xlsx",
        )
        if clicked:
            log_download_activity(user, store, title, "Excel", export_df)
    with col_pdf_data:
        clicked = st.download_button(
            "Download PDF (Data)",
            dataframe_to_pdf_bytes(export_df, title),
            file_name=f"{file_stem}_data.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"{file_stem}_pdf_data",
        )
        if clicked:
            log_download_activity(user, store, title, "PDF", export_df)
    st.markdown("</div>", unsafe_allow_html=True)


def log_download_activity(
    user: dict | None,
    store: SupabaseStore | None,
    title: str,
    file_type: str,
    export_df: pd.DataFrame,
) -> None:
    if not user or store is None:
        return
    store.log_edit_history(
        user,
        "DOWNLOAD",
        "download",
        details=f"Downloaded {file_type} file: {title}. Rows: {len(export_df)}. Columns: {', '.join(export_df.columns.astype(str).tolist())}",
    )


def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    output = BytesIO()
    safe_sheet_name = "".join(character for character in sheet_name[:31] if character not in r"[]:*?/\\")
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=safe_sheet_name or "Filtered Data")
    return output.getvalue()


def dataframe_to_pdf_bytes(df: pd.DataFrame, title: str) -> bytes:
    visible_df = df.fillna("").astype(str)
    columns = visible_df.columns.tolist()
    rows = visible_df.values.tolist()
    lines = [
        title.upper(),
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Rows exported: {len(visible_df)}",
        "",
        " | ".join(columns),
    ]
    for row in rows:
        lines.append(" | ".join(str(value) for value in row))
    return simple_pdf(lines, orientation="landscape")


def simple_pdf(lines: list[str], orientation: str = "landscape") -> bytes:
    if orientation == "portrait":
        width = 595
        height = 842
        margin_x = 42
        y_start = 794
        line_height = 14
        max_chars = 88
        lines_per_page = 53
        font_size = 9
    else:
        width = 842
        height = 595
        margin_x = 34
        y_start = 552
        line_height = 13
        max_chars = 132
        lines_per_page = 39
        font_size = 8
    pages: list[list[str]] = []
    current_page: list[str] = []

    for raw_line in lines:
        wrapped = wrap_pdf_line(raw_line, max_chars)
        for line in wrapped:
            if len(current_page) >= lines_per_page:
                pages.append(current_page)
                current_page = []
            current_page.append(line)
    if current_page:
        pages.append(current_page)

    objects: list[bytes] = []
    catalog_id = 1
    pages_id = 2
    font_id = 3
    next_id = 4
    page_ids: list[int] = []
    content_ids: list[int] = []

    for page_lines in pages:
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_ids.append(page_id)
        content_ids.append(content_id)
        stream = pdf_text_stream(page_lines, margin_x, y_start, line_height, font_size)
        objects.append(
            f"{page_id} 0 obj\n<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>\nendobj\n".encode(
                "latin-1"
            )
        )
        objects.append(
            f"{content_id} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream\nendobj\n"
        )

    page_refs = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    header_objects = [
        f"{catalog_id} 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n".encode("latin-1"),
        f"{pages_id} 0 obj\n<< /Type /Pages /Kids [{page_refs}] /Count {len(page_ids)} >>\nendobj\n".encode(
            "latin-1"
        ),
        f"{font_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode("latin-1"),
    ]
    all_objects = header_objects + objects

    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in all_objects:
        offsets.append(pdf.tell())
        pdf.write(obj)
    xref_start = pdf.tell()
    pdf.write(f"xref\n0 {len(all_objects) + 1}\n".encode("latin-1"))
    pdf.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.write(
        f"trailer\n<< /Size {len(all_objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode(
            "latin-1"
        )
    )
    return pdf.getvalue()


def pdf_text_stream(lines: list[str], x: int, y_start: int, line_height: int, font_size: int) -> bytes:
    content = ["BT", f"/F1 {font_size} Tf"]
    y = y_start
    for line in lines:
        content.append(f"1 0 0 1 {x} {y} Tm ({escape_pdf_text(line)}) Tj")
        y -= line_height
    content.append("ET")
    return "\n".join(content).encode("latin-1", errors="replace")


def wrap_pdf_line(line: str, max_chars: int) -> list[str]:
    if not line:
        return [""]
    return [line[index : index + max_chars] for index in range(0, len(line), max_chars)]


def escape_pdf_text(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def filtered_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return df[[column for column in columns if column in df.columns]].copy()


def reference_form(ref_key: str, refs: dict[str, pd.DataFrame], store: SupabaseStore) -> dict:
    payload = {}
    df = refs.get(ref_key, pd.DataFrame())
    for column in store.writable_columns(ref_key):
        sample = df[column].dropna().iloc[0] if not df[column].dropna().empty else ""
        payload[column] = st.text_input(column, value="", placeholder=str(sample))
    return payload


def field_value(row: pd.Series | None, column: str) -> str:
    if row is None or column not in row or pd.isna(row[column]):
        return ""
    return str(row[column])


def search_records(records: pd.DataFrame, query: str) -> pd.DataFrame:
    if records.empty or not query:
        return records
    search_text = query.strip().lower()
    if not search_text:
        return records
    no_matrik = records.get("NO MATRIK", pd.Series(dtype=str)).fillna("").astype(str).str.lower()
    nama_pelajar = records.get("NAMA PELAJAR", pd.Series(dtype=str)).fillna("").astype(str).str.lower()
    return records[no_matrik.str.contains(search_text, regex=False) | nama_pelajar.str.contains(search_text, regex=False)]


def record_option_map(records: pd.DataFrame) -> dict[str, object]:
    options: dict[str, object] = {}
    if records.empty:
        return options
    for _, row in records.iterrows():
        record_id = row.get("id")
        no_matrik = field_value(row, "NO MATRIK") or "-"
        nama_pelajar = field_value(row, "NAMA PELAJAR") or "Unnamed"
        kelas = field_value(row, "KELAS")
        label = f"{no_matrik} | {nama_pelajar}"
        if kelas:
            label = f"{label} | {kelas}"
        options[label] = record_id
    return options


def selected_ujian_columns(filters: dict[str, list[str]], available_columns: list[str]) -> list[str]:
    selected = [value for value in filters.get("Ujian", []) if value]
    if not selected:
        return available_columns
    return [column for column in available_columns if column in selected]


def grade_long_frame(records: pd.DataFrame, grade_columns: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for column in grade_columns:
        if column not in records.columns:
            continue
        frame = records[[column]].rename(columns={column: "GRADE"}).assign(RESULT=column)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["RESULT", "GRADE"])
    combined = pd.concat(frames, ignore_index=True)
    combined["GRADE"] = combined["GRADE"].replace({None: pd.NA}).astype("string").str.strip()
    combined = combined[combined["GRADE"].notna() & (combined["GRADE"] != "")]
    return combined


def grade_proportion_frame(grade_counts: pd.DataFrame) -> pd.DataFrame:
    if grade_counts.empty:
        return pd.DataFrame(columns=["RESULT", "GRADE", "COUNT", "PERCENT"])
    proportions = grade_counts.copy()
    totals = proportions.groupby("RESULT")["COUNT"].transform("sum")
    proportions["PERCENT"] = proportions["COUNT"] / totals * 100
    return proportions


def addmath_completion_frame(records: pd.DataFrame) -> pd.DataFrame:
    total = len(records)
    if total == 0 or "SPM_ADDMATH" not in records:
        return pd.DataFrame({"Status": ["Taken", "Not Taken"], "Count": [0, 0], "Percent": [0.0, 0.0], "Label": ["0 (0.0%)", "0 (0.0%)"]})
    taken = records["SPM_ADDMATH"].notna() & (records["SPM_ADDMATH"].astype(str).str.strip() != "")
    counts = pd.DataFrame(
        {
            "Status": ["Taken", "Not Taken"],
            "Count": [int(taken.sum()), int((~taken).sum())],
        }
    )
    counts["Percent"] = counts["Count"] / total * 100
    counts["Label"] = counts.apply(lambda row: f"{row['Count']:,} ({row['Percent']:.1f}%)", axis=1)
    return counts


def render_grade_proportion_chart(records: pd.DataFrame, columns: list[str], title: str) -> None:
    available_columns = [column for column in columns if column in records.columns]
    grade_counts = grade_long_frame(records, available_columns).value_counts(["RESULT", "GRADE"]).reset_index(name="COUNT")
    if grade_counts.empty:
        blank_state(f"No data available for {title}.")
        return
    proportions = grade_proportion_frame(grade_counts)
    fig = px.bar(
        proportions,
        x="RESULT",
        y="PERCENT",
        color="GRADE",
        title=title,
        category_orders={"GRADE": GRADE_ORDER},
        color_discrete_sequence=px.colors.qualitative.Safe,
        custom_data=["COUNT"],
    )
    fig.update_traces(
        hovertemplate="%{x}<br>Grade: %{fullData.name}<br>Percentage: %{y:.1f}%<br>Students: %{customdata[0]:,}<extra></extra>"
    )
    fig.update_layout(height=390, yaxis_title="Percent", margin=dict(l=20, r=20, t=55, b=20))
    st.plotly_chart(fig, use_container_width=True)


def count_grades(records: pd.DataFrame, column: str, grades: list[str]) -> int:
    if column not in records:
        return 0
    clean = records[column].replace({None: pd.NA}).astype("string").str.strip()
    return int(clean.isin(grades).sum())


def grade_matrix(records: pd.DataFrame, row_column: str, column_column: str) -> pd.DataFrame:
    if not {row_column, column_column}.issubset(records.columns):
        return pd.DataFrame()
    clean = records[[row_column, column_column]].copy()
    for column in [row_column, column_column]:
        clean[column] = clean[column].replace({None: pd.NA}).astype("string").str.strip()
    clean = clean.dropna(subset=[row_column, column_column])
    clean = clean[(clean[row_column] != "") & (clean[column_column] != "")]
    if clean.empty:
        return pd.DataFrame()
    return pd.crosstab(clean[row_column], clean[column_column])


def grade_order_for_column(column: str) -> list[str]:
    if column in SPM_TEST_COLUMNS:
        return SPM_GRADE_ORDER
    if column in GRADE_TEST_COLUMNS:
        return PSPM_GRADE_ORDER
    return GRADE_ORDER


def render_grade_matrix_heatmap(records: pd.DataFrame, row_column: str, column_column: str) -> None:
    matrix = grade_matrix(records, row_column, column_column)
    if matrix.empty:
        blank_state(f"No paired grades available for {row_column} and {column_column}.")
        return
    row_order = grade_order_for_column(row_column)
    column_order = grade_order_for_column(column_column)
    matrix = matrix.reindex(index=row_order, columns=column_order, fill_value=0)
    matrix = matrix.loc[matrix.sum(axis=1) > 0, matrix.sum(axis=0) > 0]
    if matrix.empty:
        blank_state(f"No paired grades available for {row_column} and {column_column}.")
        return
    export_matrix = matrix.reset_index().rename(columns={row_column: row_column})
    render_table_download_menu(
        export_matrix,
        f"{row_column}_{column_column}_matrix",
        f"{row_column} vs {column_column} Matrix",
    )

    max_count = float(matrix.to_numpy().max() or 0)
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.to_numpy(),
            x=matrix.columns.tolist(),
            y=matrix.index.tolist(),
            colorscale="YlGnBu",
            colorbar=dict(title="Count"),
            xgap=1,
            ygap=1,
            hovertemplate=f"{row_column}: %{{y}}<br>{column_column}: %{{x}}<br>Students: %{{z:,}}<extra></extra>",
        )
    )
    for row_index, row_grade in enumerate(matrix.index.tolist()):
        for column_index, column_grade in enumerate(matrix.columns.tolist()):
            value = int(matrix.loc[row_grade, column_grade])
            if value == 0:
                continue
            text_color = "#ffffff" if max_count and value >= max_count * 0.55 else "#000000"
            fig.add_annotation(
                x=column_grade,
                y=row_grade,
                text=f"{value:,}",
                showarrow=False,
                font=dict(color=text_color, size=12),
            )
    fig.update_layout(
        height=min(640, max(360, 34 * len(matrix.index) + 150)),
        xaxis_title=column_column,
        yaxis_title=row_column,
        margin=dict(l=20, r=20, t=25, b=45),
        plot_bgcolor="#ffffff",
    )
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)


def cgpa_map_for_column(column: str) -> dict[str, float]:
    if column in SPM_TEST_COLUMNS:
        return SPM_CGPA_MAP
    if column in GRADE_TEST_COLUMNS:
        return PSPM_CGPA_MAP
    return {}


def cgpa_series(values: pd.Series, column: str) -> pd.Series:
    mapping = cgpa_map_for_column(column)
    return values.astype(str).str.strip().map(mapping)


def average_cgpa_frame(records: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in columns:
        if column not in records.columns:
            continue
        cgpa = cgpa_series(records[column], column)
        valid = cgpa.dropna()
        rows.append(
            {
                "Assessment": column,
                "Average CGPA": round(float(valid.mean()), 2) if not valid.empty else None,
                "Records": int(valid.count()),
            }
        )
    return pd.DataFrame(rows)


def format_average_cgpa(records: pd.DataFrame, column: str) -> str:
    if column not in records:
        return "-"
    cgpa = cgpa_series(records[column], column).dropna()
    if cgpa.empty:
        return "-"
    return f"{cgpa.mean():.2f}"


def render_average_cgpa_comparison(records: pd.DataFrame, columns: list[str], title: str) -> None:
    comparison = average_cgpa_frame(records, columns).dropna(subset=["Average CGPA"])
    if comparison.empty:
        blank_state(f"No CGPA data available for {title}.")
        return
    fig = px.bar(
        comparison,
        x="Assessment",
        y="Average CGPA",
        color="Assessment",
        text="Average CGPA",
        title=title,
        custom_data=["Records"],
        color_discrete_sequence=["#28277f", "#0f766e", "#facc15", "#ef1c2a"],
    )
    fig.update_traces(
        texttemplate="%{text:.2f}",
        hovertemplate="%{x}<br>Average CGPA: %{y:.2f}<br>Records: %{customdata[0]:,}<extra></extra>",
    )
    fig.update_layout(height=350, yaxis_range=[0, 4], margin=dict(l=20, r=20, t=55, b=20), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def score_series(values: pd.Series, column: str) -> pd.Series:
    if column in DIAGNOSTIC_COLUMNS:
        return pd.to_numeric(values, errors="coerce")
    return cgpa_series(values, column)


def assessment_long_frame(records: pd.DataFrame, test_columns: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    identity_columns = [
        "NO MATRIK",
        "NAMA PELAJAR",
        "KELAS",
        "PENSYARAH",
        "JURUSAN",
        "PROGRAM",
        "SISTEM",
        "SUBJEK",
    ]
    available_identity = [column for column in identity_columns if column in records.columns]
    for column in test_columns:
        if column not in records.columns:
            continue
        frame = records[available_identity].copy()
        frame["Test"] = column
        frame["Raw Value"] = records[column]
        frame["Score"] = score_series(records[column], column)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=[*identity_columns, "Test", "Raw Value", "Score"])
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["Score"])
    return combined


def cgpa_long_frame(records: pd.DataFrame, test_columns: list[str], assessment_type: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    identity_columns = [
        "NO MATRIK",
        "NAMA PELAJAR",
        "KELAS",
        "PENSYARAH",
        "JURUSAN",
        "PROGRAM",
        "SISTEM",
        "SUBJEK",
    ]
    available_identity = [column for column in identity_columns if column in records.columns]
    for column in test_columns:
        if column not in records.columns:
            continue
        frame = records[available_identity].copy()
        frame["Test"] = column
        frame["Assessment Type"] = assessment_type
        frame["Raw Value"] = records[column]
        frame["CGPA"] = cgpa_series(records[column], column)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=[*identity_columns, "Test", "Assessment Type", "Raw Value", "CGPA"])
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["CGPA"])
    return combined


def overall_progress_frame(
    diagnostic_long: pd.DataFrame,
    spm_long: pd.DataFrame,
    pspm_long: pd.DataFrame,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not diagnostic_long.empty:
        diagnostic = diagnostic_long.copy()
        diagnostic["Assessment Type"] = "Diagnostic"
        diagnostic["Value"] = diagnostic["Score"] / 25
        frames.append(diagnostic)
    if not spm_long.empty:
        spm = spm_long.copy()
        spm["Value"] = spm["CGPA"]
        frames.append(spm)
    if not pspm_long.empty:
        pspm = pspm_long.copy()
        pspm["Value"] = pspm["CGPA"]
        frames.append(pspm)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).dropna(subset=["Value"])


def progress_section_for_test(
    column: str,
    diagnostic_long: pd.DataFrame,
    spm_long: pd.DataFrame,
    pspm_long: pd.DataFrame,
) -> tuple[str, pd.DataFrame, str, str, str] | None:
    if column in DIAGNOSTIC_COLUMNS:
        frame = diagnostic_long[diagnostic_long["Test"] == column]
        return column, frame, "Score", "Average Mark", "Average Mark"
    if column in SPM_TEST_COLUMNS:
        frame = spm_long[spm_long["Test"] == column]
        return column, frame, "CGPA", "Average CGPA", "Average CGPA"
    if column in GRADE_TEST_COLUMNS:
        frame = pspm_long[pspm_long["Test"] == column]
        return column, frame, "CGPA", "Average CGPA", "Average CGPA"
    return None


def ranked_metric(
    frame: pd.DataFrame,
    group_column: str,
    value_column: str,
    metric_label: str,
    base_frame: pd.DataFrame | None = None,
    assessment_column: str | None = None,
) -> pd.DataFrame:
    columns = ["Rank", group_column, metric_label, "TOTAL PELAJAR", "NO MARK/GRADE"]
    if base_frame is not None and assessment_column and group_column in base_frame and assessment_column in base_frame:
        base_clean = base_frame[
            base_frame[group_column].notna()
            & (base_frame[group_column].astype(str).str.strip() != "")
        ].copy()
        if not base_clean.empty:
            has_value = assessment_value_mask(base_clean, assessment_column)
            missing = (
                base_clean.loc[~has_value]
                .groupby(group_column)["NO MATRIK"]
                .nunique()
                .reset_index(name="NO MARK/GRADE")
            )
            all_groups = (
                base_clean.groupby(group_column)["NO MATRIK"]
                .nunique()
                .reset_index(name="TOTAL PELAJAR")
            )
        else:
            missing = pd.DataFrame(columns=[group_column, "NO MARK/GRADE"])
            all_groups = pd.DataFrame(columns=[group_column, "TOTAL PELAJAR"])
    else:
        missing = pd.DataFrame(columns=[group_column, "NO MARK/GRADE"])
        all_groups = pd.DataFrame(columns=[group_column, "TOTAL PELAJAR"])

    if frame.empty or group_column not in frame or value_column not in frame:
        rank = all_groups.assign(**{metric_label: pd.NA, "_VALID_PELAJAR": 0})
    else:
        clean = frame[
            frame[group_column].notna()
            & (frame[group_column].astype(str).str.strip() != "")
            & frame[value_column].notna()
        ].copy()
        if clean.empty:
            rank = all_groups.assign(**{metric_label: pd.NA, "_VALID_PELAJAR": 0})
        else:
            rank = (
                clean.groupby(group_column)
                .agg(
                    **{
                        metric_label: (value_column, "mean"),
                        "_VALID_PELAJAR": ("NO MATRIK", "nunique"),
                    }
                )
                .reset_index()
            )
            if not all_groups.empty:
                rank = all_groups.merge(rank, on=group_column, how="left")
                rank["_VALID_PELAJAR"] = rank["_VALID_PELAJAR"].fillna(0).astype(int)
            rank = rank.sort_values(metric_label, ascending=False, na_position="last")

    if not missing.empty:
        rank = rank.merge(missing, on=group_column, how="left")
    elif "NO MARK/GRADE" not in rank:
        rank["NO MARK/GRADE"] = 0
    rank["NO MARK/GRADE"] = rank["NO MARK/GRADE"].fillna(0).astype(int)
    if "TOTAL PELAJAR" not in rank:
        valid_count = rank["_VALID_PELAJAR"] if "_VALID_PELAJAR" in rank else 0
        rank["TOTAL PELAJAR"] = valid_count + rank["NO MARK/GRADE"]
    rank["TOTAL PELAJAR"] = rank["TOTAL PELAJAR"].fillna(0).astype(int)
    if "_VALID_PELAJAR" in rank:
        rank = rank.drop(columns=["_VALID_PELAJAR"])
    if rank.empty:
        return pd.DataFrame(columns=columns)
    rank = rank.sort_values(metric_label, ascending=False, na_position="last").reset_index(drop=True)
    rank.insert(0, "Rank", range(1, len(rank) + 1))
    rank[metric_label] = pd.to_numeric(rank[metric_label], errors="coerce").round(2)
    return rank[[column for column in columns if column in rank.columns]]


def assessment_value_mask(records: pd.DataFrame, assessment_column: str) -> pd.Series:
    if assessment_column not in records:
        return pd.Series(False, index=records.index)
    if assessment_column in DIAGNOSTIC_COLUMNS:
        return pd.to_numeric(records[assessment_column], errors="coerce").notna()
    if assessment_column in [*SPM_TEST_COLUMNS, *GRADE_TEST_COLUMNS]:
        return cgpa_series(records[assessment_column], assessment_column).notna()
    return records[assessment_column].notna() & (records[assessment_column].astype(str).str.strip() != "")


def system_filtered_records(records: pd.DataFrame, system_label: str) -> pd.DataFrame:
    if system_label == "Overall" or "SISTEM" not in records:
        return records
    return records[
        records["SISTEM"].fillna("").astype(str).str.upper().str.strip() == system_label
    ]


def selected_plotly_points(event: object) -> list[dict]:
    if not event:
        return []
    try:
        selection = event.get("selection", {})
    except AttributeError:
        selection = getattr(event, "selection", {})
    if not selection:
        return []
    try:
        return selection.get("points", []) or []
    except AttributeError:
        return getattr(selection, "points", []) or []


def selected_dataframe_rows(event: object) -> list[int]:
    if not event:
        return []
    try:
        selection = event.get("selection", {})
    except AttributeError:
        selection = getattr(event, "selection", {})
    if not selection:
        return []
    try:
        return selection.get("rows", []) or []
    except AttributeError:
        return getattr(selection, "rows", []) or []


def render_selected_students(title: str, frame: pd.DataFrame) -> None:
    if frame.empty:
        blank_state("No students match the selected item.")
        return
    columns = [column for column in STUDENT_DETAIL_COLUMNS if column in frame.columns]
    detail = frame[columns].drop_duplicates().sort_values(
        [column for column in ["NAMA PELAJAR", "NO MATRIK"] if column in columns],
        na_position="last",
    )
    st.markdown(f"**{title}**")
    render_data_table(detail, f"selected_students_{safe_key(title)}", title)


def render_progress_section(
    frame: pd.DataFrame,
    group_column: str,
    section_label: str,
    value_column: str,
    metric_label: str,
    axis_title: str,
    base_records: pd.DataFrame,
) -> None:
    system_tabs = st.tabs(["Overall", "SES", "SDS"])
    for tab, (system_label, system_frame) in zip(system_tabs, split_system_frames(frame)):
        with tab:
            system_base = system_filtered_records(base_records, system_label)
            render_progress_assessment_cards(system_base, system_frame, section_label, value_column, metric_label)
            rank = ranked_metric(
                system_frame,
                group_column,
                value_column,
                metric_label,
                system_base,
                section_label,
            )
            selected_groups: list[str] = []
            left, right = st.columns([1.1, 1])
            with left:
                selected_groups.extend(
                    render_rank_chart(
                    rank,
                    group_column,
                    f"{section_label} {system_label} Rank",
                    metric_label,
                    axis_title,
                    f"{group_column}_{section_label}_{system_label}_rank_chart",
                    )
                )
            with right:
                if rank.empty:
                    blank_state(f"No {section_label.lower()} records for {system_label}.")
                else:
                    rank_title = f"{group_column} {section_label} {system_label} Rank"
                    render_table_download_menu(rank, safe_key(rank_title), rank_title)
                    try:
                        table_event = st.dataframe(
                            rank,
                            hide_index=True,
                            use_container_width=True,
                            on_select="rerun",
                            selection_mode="single-row",
                            key=f"{group_column}_{section_label}_{system_label}_rank_table",
                        )
                        for row_index in selected_dataframe_rows(table_event):
                            if 0 <= row_index < len(rank):
                                selected_groups.append(str(rank.iloc[row_index][group_column]))
                    except TypeError:
                        st.dataframe(rank, hide_index=True, use_container_width=True)
            if selected_groups and group_column in system_frame.columns:
                selected_set = {str(value) for value in selected_groups}
                selected_frame = system_frame[system_frame[group_column].astype(str).isin(selected_set)]
                render_selected_students(
                    f"Selected Students: {', '.join(sorted(selected_set))}",
                    selected_frame,
                )
            render_progress_distribution(system_frame, group_column, section_label, system_label)


def render_progress_assessment_cards(
    base_frame: pd.DataFrame,
    assessment_frame: pd.DataFrame,
    assessment_column: str,
    value_column: str,
    metric_label: str,
) -> None:
    total_students = int(base_frame["NO MATRIK"].nunique()) if "NO MATRIK" in base_frame else 0
    has_value_mask = assessment_value_mask(base_frame, assessment_column)
    students_with_value = int(base_frame.loc[has_value_mask, "NO MATRIK"].nunique()) if "NO MATRIK" in base_frame else 0
    students_missing = max(total_students - students_with_value, 0)
    average_value = pd.to_numeric(assessment_frame.get(value_column, pd.Series(dtype=float)), errors="coerce").dropna()
    average_label = "Average Mark" if assessment_column in DIAGNOSTIC_COLUMNS else "Average CGPA"
    average_display = "-" if average_value.empty else f"{average_value.mean():.2f}"

    cards = st.columns(4)
    cards[0].metric("TOTAL PELAJAR", f"{total_students:,}")
    cards[1].metric("HAS MARK/GRADE", f"{students_with_value:,}")
    cards[2].metric("NO MARK/GRADE", f"{students_missing:,}")
    cards[3].metric(average_label, average_display)


def render_progress_distribution(
    frame: pd.DataFrame,
    group_column: str,
    section_label: str,
    system_label: str,
) -> None:
    if section_label in [*SPM_TEST_COLUMNS, *GRADE_TEST_COLUMNS]:
        render_progress_grade_heatmap(frame, group_column, section_label, system_label)
    elif section_label in DIAGNOSTIC_COLUMNS:
        render_diagnostic_mark_distribution(frame, section_label, system_label)


def render_progress_grade_heatmap(
    frame: pd.DataFrame,
    group_column: str,
    test_name: str,
    system_label: str,
) -> None:
    if frame.empty or group_column not in frame or "Raw Value" not in frame:
        return
    clean = frame[[group_column, "Raw Value"]].copy()
    clean[group_column] = clean[group_column].astype("string").str.strip()
    clean["GRADE"] = clean["Raw Value"].astype("string").str.strip()
    clean = clean[
        clean[group_column].notna()
        & (clean[group_column] != "")
        & clean["GRADE"].notna()
        & (clean["GRADE"] != "")
    ]
    if clean.empty:
        return

    grade_order = SPM_GRADE_ORDER if test_name in SPM_TEST_COLUMNS else PSPM_GRADE_ORDER
    matrix = pd.crosstab(clean[group_column], clean["GRADE"]).reindex(columns=grade_order, fill_value=0)
    matrix = matrix.loc[matrix.sum(axis=1) > 0]
    if matrix.empty:
        return

    max_groups = 30
    if len(matrix) > max_groups:
        top_index = matrix.sum(axis=1).sort_values(ascending=False).head(max_groups).index
        matrix = matrix.loc[top_index]
        st.caption(f"Grade heatmap shows the {max_groups} largest {group_column.lower()} groups by available result count.")

    heatmap_points = matrix.reset_index().melt(
        id_vars=group_column,
        var_name="Grade",
        value_name="Students",
    )
    group_order = matrix.index.tolist()
    grade_positions = {grade: index + 1 for index, grade in enumerate(grade_order)}
    group_positions = {group: index for index, group in enumerate(group_order)}
    heatmap_points["Grade Position"] = heatmap_points["Grade"].map(grade_positions)
    heatmap_points["Row Position"] = heatmap_points[group_column].map(group_positions)
    heatmap_points["Label"] = heatmap_points["Students"].map(lambda value: f"{int(value):,}" if value else "")
    max_students = float(heatmap_points["Students"].max() or 0)
    heatmap_points["Text Color Group"] = heatmap_points["Students"].apply(
        lambda value: "Light text" if max_students and value >= max_students * 0.55 else "Dark text"
    )
    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=matrix.to_numpy(),
            x=[grade_positions[grade] for grade in grade_order],
            y=list(range(len(group_order))),
            colorscale="YlGnBu",
            colorbar=dict(title="Students"),
            xgap=1,
            ygap=1,
            hoverinfo="skip",
        )
    )
    for row_position in range(len(group_order)):
        fig.add_shape(
            type="rect",
            x0=-0.5,
            x1=0.5,
            y0=row_position - 0.5,
            y1=row_position + 0.5,
            fillcolor="#f8fafc",
            line=dict(color="#e7ebf3", width=1),
            layer="below",
        )
    fig.add_trace(
        go.Scatter(
            x=[0] * len(group_order),
            y=list(range(len(group_order))),
            mode="text",
            text=group_order,
            textposition="middle center",
            textfont=dict(color="#000000", size=11),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    for text_group, text_color in [("Dark text", "#000000"), ("Light text", "#ffffff")]:
        layer = heatmap_points[heatmap_points["Text Color Group"] == text_group]
        if layer.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=layer["Grade Position"],
                y=layer["Row Position"],
                mode="text",
                text=layer["Label"],
                textposition="middle center",
                textfont=dict(color=text_color, size=12),
                customdata=layer[[group_column, "Grade", "Students"]].to_numpy(),
                hovertemplate=f"{group_column}: %{{customdata[0]}}<br>Grade: %{{customdata[1]}}<br>Students: %{{customdata[2]:,}}<extra></extra>",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=heatmap_points["Grade Position"],
            y=heatmap_points["Row Position"],
            mode="markers",
            customdata=heatmap_points[[group_column, "Grade", "Students"]].to_numpy(),
            marker=dict(symbol="square", size=30, color="rgba(0,0,0,0.01)", line=dict(width=0)),
            hovertemplate=f"{group_column}: %{{customdata[0]}}<br>Grade: %{{customdata[1]}}<br>Students: %{{customdata[2]:,}}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        title=f"{test_name} Grade Distribution Heatmap ({system_label})",
        height=min(860, max(380, 30 * len(matrix) + 150)),
        xaxis_title="Grade",
        yaxis_title="",
        showlegend=False,
        clickmode="event+select",
        margin=dict(l=20, r=20, t=55, b=35),
        plot_bgcolor="#ffffff",
    )
    fig.update_xaxes(
        range=[-0.5, len(grade_order) + 0.5],
        tickmode="array",
        tickvals=[0, *[grade_positions[grade] for grade in grade_order]],
        ticktext=[group_column, *grade_order],
        gridcolor="#e7ebf3",
        zeroline=False,
    )
    fig.update_yaxes(
        range=[len(group_order) - 0.5, -0.5],
        tickmode="array",
        tickvals=list(range(len(group_order))),
        ticktext=[""] * len(group_order),
        showticklabels=False,
        gridcolor="#e7ebf3",
        zeroline=False,
    )
    chart_key = f"{group_column}_{test_name}_{system_label}_grade_heatmap"
    try:
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            key=chart_key,
            on_select="rerun",
            selection_mode="points",
        )
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=chart_key)
        return

    points = selected_plotly_points(event)
    if not points:
        return
    point = points[0]
    custom_data = point.get("customdata")
    selected_group = ""
    selected_grade = ""
    if isinstance(custom_data, (list, tuple)) and len(custom_data) >= 2:
        selected_group = str(custom_data[0]).strip()
        selected_grade = str(custom_data[1]).strip()
    if not selected_group:
        try:
            selected_group = str(group_order[int(round(float(point.get("y"))))]).strip()
        except (TypeError, ValueError, IndexError):
            selected_group = str(point.get("y", "")).strip()
    if not selected_grade:
        try:
            selected_grade = str(grade_order[int(round(float(point.get("x")))) - 1]).strip()
        except (TypeError, ValueError, IndexError):
            selected_grade = str(point.get("x", "")).strip()
    if not selected_group or not selected_grade:
        return
    selected_frame = frame[
        (frame[group_column].astype(str).str.strip() == selected_group)
        & (frame["Raw Value"].astype("string").str.strip() == selected_grade)
    ]
    render_selected_students(
        f"Selected Students: {selected_group} | {test_name} {selected_grade}",
        selected_frame,
    )


def render_diagnostic_mark_distribution(frame: pd.DataFrame, test_name: str, system_label: str) -> None:
    if frame.empty or "Score" not in frame:
        return
    scores = pd.to_numeric(frame["Score"], errors="coerce").dropna()
    if scores.empty:
        return
    distribution = scores.round(2).value_counts().sort_index().reset_index()
    distribution.columns = ["Mark", "Students"]
    distribution["Mark Label"] = distribution["Mark"].map(lambda value: f"{value:g}")
    total = distribution["Students"].sum()
    distribution["Percent"] = distribution["Students"] / total * 100 if total else 0

    fig = px.bar(
        distribution,
        x="Mark Label",
        y="Students",
        color="Students",
        text="Students",
        title=f"{test_name} Mark Distribution ({system_label})",
        custom_data=["Mark", "Percent"],
        color_continuous_scale="YlGnBu",
    )
    fig.update_traces(
        texttemplate="%{text:,}",
        textposition="outside",
        hovertemplate="Mark: %{customdata[0]:g}<br>Students: %{y:,}<br>Percent: %{customdata[1]:.1f}%<extra></extra>",
    )
    fig.update_layout(
        height=min(520, max(340, 14 * len(distribution) + 260)),
        yaxis_title="Students",
        xaxis_title="Mark",
        showlegend=False,
        clickmode="event+select",
        margin=dict(l=20, r=20, t=55, b=20),
    )
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=distribution["Mark Label"].tolist())
    chart_key = f"{test_name}_{system_label}_diagnostic_distribution"
    try:
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            key=chart_key,
            on_select="rerun",
            selection_mode="points",
        )
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=chart_key)
        return

    points = selected_plotly_points(event)
    if not points:
        return
    point = points[0]
    selected_mark = point.get("x")
    if selected_mark is None:
        custom_data = point.get("customdata")
        if isinstance(custom_data, (list, tuple)) and custom_data:
            selected_mark = custom_data[0]
        elif custom_data is not None and hasattr(custom_data, "__len__") and not isinstance(custom_data, str):
            try:
                selected_mark = custom_data[0]
            except Exception:
                selected_mark = custom_data
        else:
            selected_mark = custom_data
    if selected_mark is None:
        point_number = point.get(
            "point_number",
            point.get("pointNumber", point.get("pointIndex", point.get("point_index"))),
        )
        try:
            point_index = int(point_number)
        except (TypeError, ValueError):
            point_index = None
        if point_index is not None and 0 <= point_index < len(distribution):
            selected_mark = distribution.iloc[point_index]["Mark"]
    selected_mark_value = pd.to_numeric(pd.Series([selected_mark]), errors="coerce").iloc[0]
    if pd.isna(selected_mark_value):
        return
    selected_frame = frame[pd.to_numeric(frame["Score"], errors="coerce").round(2) == round(float(selected_mark_value), 2)]
    render_selected_students(
        f"Selected Students: {test_name} Mark {selected_mark_value:g}",
        selected_frame,
    )


def ranked_performance(performance_long: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if performance_long.empty or group_column not in performance_long:
        return pd.DataFrame(columns=["Rank", group_column, "Average Score", "PELAJAR"])
    performance_long = performance_long[
        performance_long[group_column].notna()
        & (performance_long[group_column].astype(str).str.strip() != "")
    ].copy()
    if performance_long.empty:
        return pd.DataFrame(columns=["Rank", group_column, "Average Score", "PELAJAR"])
    rank = (
        performance_long.groupby(group_column)
        .agg(
            **{
                "Average Score": ("Score", "mean"),
                "PELAJAR": ("NO MATRIK", "nunique"),
            }
        )
        .reset_index()
        .sort_values("Average Score", ascending=False)
    )
    rank.insert(0, "Rank", range(1, len(rank) + 1))
    rank["Average Score"] = rank["Average Score"].round(1)
    return rank


def split_system_frames(performance_long: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    frames = [("Overall", performance_long)]
    for system in ["SES", "SDS"]:
        if "SISTEM" not in performance_long:
            frames.append((system, performance_long.iloc[0:0]))
            continue
        system_frame = performance_long[
            performance_long["SISTEM"].fillna("").astype(str).str.upper().str.strip() == system
        ]
        frames.append((system, system_frame))
    return frames


def render_rank_chart(
    rank: pd.DataFrame,
    group_column: str,
    title: str,
    metric_label: str,
    axis_title: str,
    chart_key: str,
) -> list[str]:
    chart_rank = rank.dropna(subset=[metric_label]) if metric_label in rank else rank
    if chart_rank.empty:
        blank_state(f"No records for {title}.")
        return []
    fig = px.bar(
        chart_rank.head(12),
        x=metric_label,
        y=group_column,
        orientation="h",
        title=title,
        color=metric_label,
        color_continuous_scale="YlGnBu",
        hover_data=[column for column in ["Rank", "TOTAL PELAJAR", "NO MARK/GRADE"] if column in chart_rank.columns],
    )
    fig.update_layout(
        height=390,
        xaxis_title=axis_title,
        yaxis={"categoryorder": "total ascending"},
        margin=dict(l=20, r=20, t=55, b=20),
    )
    try:
        event = st.plotly_chart(
            fig,
            use_container_width=True,
            key=chart_key,
            on_select="rerun",
            selection_mode="points",
        )
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=chart_key)
        return []
    return [
        str(point.get("y")).strip()
        for point in selected_plotly_points(event)
        if point.get("y") is not None and str(point.get("y")).strip()
    ]


def split_people(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def count_people(values: pd.Series) -> int:
    return len({name for value in values.dropna() for name in split_people(value)})


def lecturer_count_frame(records: pd.DataFrame) -> pd.DataFrame:
    if "PENSYARAH" not in records:
        return pd.DataFrame(columns=["Pensyarah", "Records"])
    lecturer_rows = records[["PENSYARAH"]].copy()
    lecturer_rows["Pensyarah"] = lecturer_rows["PENSYARAH"].apply(split_people)
    lecturer_rows = lecturer_rows.explode("Pensyarah")
    lecturer_rows = lecturer_rows[
        lecturer_rows["Pensyarah"].notna() & (lecturer_rows["Pensyarah"].astype(str).str.strip() != "")
    ]
    if lecturer_rows.empty:
        return pd.DataFrame(columns=["Pensyarah", "Records"])
    return (
        lecturer_rows.groupby("Pensyarah")
        .size()
        .reset_index(name="Records")
        .sort_values("Records", ascending=False)
    )


def main() -> None:
    store = SupabaseStore()

    if "user" not in st.session_state:
        login_screen(store)
        return

    user = st.session_state.user
    render_user_badge(user)
    if st.session_state.pop("supabase_data_dirty", False):
        store.refresh_cache()
    loading_slot = st.empty()
    with loading_slot.container():
        page_header(
            "Loading Dashboard",
            "Preparing Supabase data and loading your assigned pages.",
            user["role"],
        )
        st.info("Loading data from Supabase...")

    base_records = store.fetch_base_records(user, results_mode="none")
    page, filters = sidebar_navigation(user, store, base_records)
    if page in [
        "PSPM ANALYSIS",
        "DIAGNOSTIC ANALYSIS",
        "LECTURER PROGRESS",
        "CLASS PROGRESS",
        "PROGRAM PROGRESS",
        "DOWNLOAD",
    ]:
        base_records = store.fetch_base_records(user, results_mode="all")
    elif page in ["SPM ANALYSIS", "DATA MANAGEMENT"]:
        base_records = store.fetch_base_records(user, results_mode="spm")
    records = store.filter_records(base_records, filters)
    loading_slot.empty()

    if page == "DEMOGRAPHY":
        demography_dashboard(records, user)
    elif page == "SPM ANALYSIS":
        results_dashboard(records, user, filters)
    elif page == "PSPM ANALYSIS":
        pspm_analysis_page(records, user, filters)
    elif page == "DIAGNOSTIC ANALYSIS":
        diagnostic_dashboard(records, user, filters)
    elif page == "LECTURER PROGRESS":
        lecturer_progress_page(records, user, filters)
    elif page == "CLASS PROGRESS":
        class_progress_page(records, user, filters)
    elif page == "PROGRAM PROGRESS":
        program_progress_page(records, user, filters)
    elif page == "DOWNLOAD":
        download_page(records, user, store)
    elif page == "ADMIN":
        admin_page(user, store)
    elif page == "DATA MANAGEMENT":
        data_management_page(records, user, store)


if __name__ == "__main__":
    main()
