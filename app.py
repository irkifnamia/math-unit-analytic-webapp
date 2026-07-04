from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from components.ui import afj_sidebar_brand, app_brand, blank_state, inject_theme, page_header
from services.supabase_store import (
    natural_key_column,
    SupabaseStore,
)


GRADE_ORDER = ["A+", "A", "A-", "B+", "B", "C+", "C", "D", "E", "G"]
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
GRADE_SCORE_MAP = {
    "A+": 100,
    "A": 95,
    "A-": 90,
    "B+": 85,
    "B": 80,
    "B-": 75,
    "C+": 70,
    "C": 65,
    "D": 50,
    "E": 40,
    "G": 30,
}


DUMMY_IC_USERS = {
    "900101145555": {
        "full_name": "Temporary Admin",
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
            user = authenticate_ic_number(ic_number)
            if user:
                st.session_state.user = user
                st.rerun()
            st.error("This IC Number is not allowed yet.")
            st.caption("Temporary allowed ICs: 900101145555, 850505105555, 880808085555")


def authenticate_ic_number(ic_number: str) -> dict | None:
    normalized_ic = normalize_ic_number(ic_number)
    allowed_users = allowed_ic_users()
    user = allowed_users.get(normalized_ic)
    if not user:
        return None
    return {
        "id": normalized_ic,
        "ic_number": normalized_ic,
        "email": None,
        **user,
    }


def allowed_ic_users() -> dict[str, dict]:
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


def normalize_ic_number(ic_number: str) -> str:
    return "".join(character for character in str(ic_number) if character.isdigit())


def sidebar_navigation(
    user: dict,
    store: SupabaseStore,
    base_records: pd.DataFrame,
) -> tuple[str, dict[str, list[str]]]:
    with st.sidebar:
        app_brand()
    st.sidebar.caption(f"{user['full_name']} | {user['role']}")

    role_pages = {
        "Admin": [
            "DEMOGRAPHY",
            "SPM ANALYSIS",
            "PSPM ANALYSIS",
            "DIAGNOSTIC ANALYSIS",
            "LECTURER PROGRESS",
            "CLASS PROGRESS",
            "DOWNLOAD",
            "DATA MANAGEMENT",
        ],
        "Executive": [
            "DEMOGRAPHY",
            "SPM ANALYSIS",
            "PSPM ANALYSIS",
            "DIAGNOSTIC ANALYSIS",
            "LECTURER PROGRESS",
            "CLASS PROGRESS",
            "DOWNLOAD",
        ],
        "Lecturer": [
            "DEMOGRAPHY",
            "SPM ANALYSIS",
            "PSPM ANALYSIS",
            "DIAGNOSTIC ANALYSIS",
            "LECTURER PROGRESS",
            "CLASS PROGRESS",
            "DOWNLOAD",
        ],
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
        disabled = user["role"] == "Lecturer" and label == "Pensyarah"
        key = f"global_filter_{label}"
        selected_values = st.session_state.get(key, [])
        st.session_state[key] = [value for value in selected_values if value in values]
        if disabled and values and not st.session_state[key]:
            st.session_state[key] = values
        filters[label] = st.sidebar.multiselect(
            label,
            values,
            key=key,
            placeholder=f"All {label}",
            disabled=disabled,
        )
    if user["role"] == "Lecturer":
        st.sidebar.caption("Lecturer access is scoped to your own records.")

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
    st.dataframe(
        records[
            [
                "NO MATRIK",
                "NAMA PELAJAR",
                "JURUSAN",
                "SISTEM",
                "KELAS",
                "SUBJEK",
                "PROGRAM",
                "PENSYARAH",
            ]
        ],
        use_container_width=True,
        hide_index=True,
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
    kpis[2].metric("SPM Math Grades", f"{spm_records['SPM_MATH'].nunique():,}" if "SPM_MATH" in spm_records else "0")
    kpis[3].metric("SPM Add Math Grades", f"{spm_records['SPM_ADDMATH'].nunique():,}" if "SPM_ADDMATH" in spm_records else "0")

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

    st.subheader("SPM ADDMATH vs SPM MATH Grade Matrix")
    if {"SPM_MATH", "SPM_ADDMATH"}.issubset(selected_spm_columns):
        render_grade_matrix(spm_records, "SPM_MATH", "SPM_ADDMATH")
    else:
        blank_state("Select both SPM_MATH and SPM_ADDMATH in Ujian to view the grade matrix.")

    st.subheader("Filtered SPM Records")
    st.dataframe(
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
        use_container_width=True,
        hide_index=True,
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
    kpis[0].metric("Students", f"{pspm_records['NO MATRIK'].nunique():,}" if "NO MATRIK" in pspm_records else "0")
    kpis[1].metric("DM015 Records", f"{pspm_records['PSPM_DM015'].notna().sum():,}" if "PSPM_DM015" in pspm_records else "0")
    kpis[2].metric("DM025 Records", f"{pspm_records['PSPM_DM025'].notna().sum():,}" if "PSPM_DM025" in pspm_records else "0")
    kpis[3].metric("SEM Results", f"{pspm_records[['PSPM_SEM1', 'PSPM_SEM2']].notna().sum().sum():,}" if {"PSPM_SEM1", "PSPM_SEM2"}.issubset(pspm_records.columns) else "0")

    left, right = st.columns(2)
    with left:
        render_grade_proportion_chart(pspm_records, ["PSPM_DM015", "PSPM_DM025"], "PSPM DM015 vs PSPM DM025 Grade Proportion")
    with right:
        render_grade_proportion_chart(pspm_records, ["PSPM_SEM1", "PSPM_SEM2"], "PSPM SEM1 vs PSPM SEM2 Grade Proportion")

    left, right = st.columns(2)
    with left:
        st.subheader("PSPM DM015 vs PSPM DM025 Matrix")
        render_grade_matrix(pspm_records, "PSPM_DM015", "PSPM_DM025")
    with right:
        st.subheader("PSPM SEM1 vs PSPM SEM2 Matrix")
        render_grade_matrix(pspm_records, "PSPM_SEM1", "PSPM_SEM2")

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
    st.dataframe(pspm_records[[col for col in display_cols if col in pspm_records.columns]], hide_index=True, use_container_width=True)


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
    st.dataframe(records[[col for col in display_cols if col in records.columns]], hide_index=True, use_container_width=True)


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


def progress_rank_page(records: pd.DataFrame, filters: dict[str, list[str]], group_column: str, group_label: str) -> None:
    type_columns = {
        "Diagnostic": selected_ujian_columns(filters, DIAGNOSTIC_COLUMNS),
        "SPM": selected_ujian_columns(filters, SPM_TEST_COLUMNS),
        "PSPM": selected_ujian_columns(filters, GRADE_TEST_COLUMNS),
    }
    active_columns = [column for columns in type_columns.values() for column in columns]
    if not active_columns:
        blank_state("The selected Ujian filter does not include diagnostic, SPM, or PSPM assessments.")
        return
    performance_long = assessment_long_frame(records, active_columns)
    if performance_long.empty:
        blank_state("No assessment data match the selected filters.")
        return

    kpis = st.columns(4)
    kpis[0].metric("Students", f"{performance_long['NO MATRIK'].nunique():,}")
    kpis[1].metric("Assessments", f"{performance_long['Test'].nunique():,}")
    kpis[2].metric("Overall Score", f"{performance_long['Score'].mean():.1f}")
    kpis[3].metric(f"{group_label}s", f"{performance_long[group_column].nunique():,}" if group_column in performance_long else "0")

    for system_label, system_frame in split_system_frames(performance_long):
        st.subheader(system_label)
        cols = st.columns(3)
        for index, (assessment_type, columns) in enumerate(type_columns.items()):
            with cols[index]:
                type_frame = system_frame[system_frame["Test"].isin(columns)] if columns else system_frame.iloc[0:0]
                rank = ranked_performance(type_frame, group_column)
                render_rank_chart(
                    rank,
                    group_column,
                    f"{system_label} {assessment_type} Rank",
                    f"{group_column}_{system_label}_{assessment_type}_rank_chart",
                )
        table_tabs = st.tabs(["Diagnostic", "SPM", "PSPM"])
        for tab, (assessment_type, columns) in zip(table_tabs, type_columns.items()):
            with tab:
                type_frame = system_frame[system_frame["Test"].isin(columns)] if columns else system_frame.iloc[0:0]
                rank = ranked_performance(type_frame, group_column)
                if rank.empty:
                    blank_state(f"No {assessment_type.lower()} records for {system_label}.")
                else:
                    st.dataframe(rank, hide_index=True, use_container_width=True)


def download_page(records: pd.DataFrame, user: dict) -> None:
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
    st.dataframe(export_df.head(500), hide_index=True, use_container_width=True)
    render_download_buttons(export_df, "custom_download_filtered_data", "Custom Download Data")


def data_management_page(records: pd.DataFrame, user: dict, store: SupabaseStore) -> None:
    page_header(
        "DATA MANAGEMENT",
        "Create, update, delete, import, and validate academic records.",
        user["role"],
    )
    if user["role"] != "Admin":
        st.error("You do not have permission to access DATA MANAGEMENT.")
        return

    render_data_management_success()
    refs = store.get_reference_data()
    dataset_label = st.selectbox("Dataset", list(DATASET_OPTIONS.keys()), key="dm_dataset")
    dataset_key = DATASET_OPTIONS[dataset_label]
    dataset = dataset_frame(dataset_key, refs)
    writable_columns = store.writable_columns(dataset_key)
    tab_records, tab_form, tab_import, tab_refs = st.tabs(
        ["Records", "Create or Update", "Bulk Import", "Reference Data"]
    )

    with tab_records:
        st.subheader(f"{dataset_label} Records")
        st.caption("Search, review, and delete records from the selected Supabase dataset.")
        record_search = st.text_input(
            "Search records",
            placeholder=dataset_search_placeholder(dataset_key),
            key="delete_record_search",
        )
        record_candidates = search_dataset(dataset, record_search, dataset_key)
        st.dataframe(record_candidates, hide_index=True, use_container_width=True)
        delete_options = dataset_option_map(record_candidates, dataset_key)
        selected_labels = st.multiselect("Select records to delete", list(delete_options.keys()))
        selected_ids = [delete_options[label] for label in selected_labels]
        if st.button("Delete selected records", type="secondary", disabled=not selected_ids):
            deleted = store.delete_reference(dataset_key, selected_ids)
            set_data_management_success(f"Successfully deleted {deleted} {dataset_label.lower()} record(s).")
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
                store.upsert_reference(dataset_key, payload, None if selected == "New record" else update_options[selected])
                action = "created" if selected == "New record" else "updated"
                set_data_management_success(f"Successfully {action} {dataset_label.lower()} record.")
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
                    preview, errors = validate_selected_import_frame(
                        incoming,
                        dataset_key,
                        writable_columns,
                        selected_update_columns,
                        match_column,
                    )
                    st.subheader("Preview")
                    st.dataframe(preview, hide_index=True, use_container_width=True)
                    if errors:
                        st.error("Please fix the validation errors before saving.")
                        st.write(errors)
                    elif st.button("Save imported data", type="primary"):
                        saved = store.bulk_upsert_reference(dataset_key, preview)
                        set_data_management_success(
                            f"Bulk import successful. {saved} {dataset_label.lower()} record(s) saved."
                        )
                        st.rerun()
                except Exception as exc:
                    st.error(f"Unable to read uploaded file: {exc}")

    with tab_refs:
        st.subheader(f"{dataset_label} Reference Data")
        st.dataframe(dataset, hide_index=True, use_container_width=True)
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


def render_data_management_success() -> None:
    message = st.session_state.pop("data_management_success", None)
    if not message:
        return
    st.success(message, icon="✅")
    try:
        st.toast(message, icon="✅")
    except Exception:
        pass


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
        update_values = [row.get(column, "") for column in allowed_update_columns]
        if not any(value != "" for value in update_values):
            errors.append(f"Row {row_number + 2}: at least one selected update column is required")

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


def render_download_buttons(df: pd.DataFrame, file_stem: str, title: str) -> None:
    export_df = df.copy()
    if export_df.empty:
        return
    st.markdown('<div class="download-strip">', unsafe_allow_html=True)
    col_csv, col_excel, col_pdf_data, spacer = st.columns([1, 1, 1.2, 4.8])
    with col_csv:
        st.download_button(
            "Download CSV",
            export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{file_stem}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"{file_stem}_csv",
        )
    with col_excel:
        st.download_button(
            "Download Excel",
            dataframe_to_excel_bytes(export_df, title),
            file_name=f"{file_stem}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"{file_stem}_xlsx",
        )
    with col_pdf_data:
        st.download_button(
            "Download PDF (Data)",
            dataframe_to_pdf_bytes(export_df, title),
            file_name=f"{file_stem}_data.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"{file_stem}_pdf_data",
        )
    st.markdown("</div>", unsafe_allow_html=True)


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


def render_grade_matrix(records: pd.DataFrame, row_column: str, column_column: str) -> None:
    matrix = grade_matrix(records, row_column, column_column)
    if matrix.empty:
        blank_state(f"No paired grades available for {row_column} and {column_column}.")
        return
    matrix = matrix.reindex(index=GRADE_ORDER, columns=GRADE_ORDER, fill_value=0).dropna(how="all")
    st.dataframe(matrix, use_container_width=True)


def score_series(values: pd.Series, column: str) -> pd.Series:
    if column in DIAGNOSTIC_COLUMNS:
        return pd.to_numeric(values, errors="coerce")
    return values.astype(str).str.strip().map(GRADE_SCORE_MAP)


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


def ranked_performance(performance_long: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if performance_long.empty or group_column not in performance_long:
        return pd.DataFrame(columns=["Rank", group_column, "Average Score", "Records", "Students"])
    performance_long = performance_long[
        performance_long[group_column].notna()
        & (performance_long[group_column].astype(str).str.strip() != "")
    ].copy()
    if performance_long.empty:
        return pd.DataFrame(columns=["Rank", group_column, "Average Score", "Records", "Students"])
    rank = (
        performance_long.groupby(group_column)
        .agg(
            **{
                "Average Score": ("Score", "mean"),
                "Records": ("Score", "count"),
                "Students": ("NO MATRIK", "nunique"),
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


def render_rank_chart(rank: pd.DataFrame, group_column: str, title: str, chart_key: str) -> None:
    if rank.empty:
        blank_state(f"No records for {title}.")
        return
    fig = px.bar(
        rank.head(12),
        x="Average Score",
        y=group_column,
        orientation="h",
        title=title,
        color="Average Score",
        color_continuous_scale="YlGnBu",
        hover_data=["Rank", "Records", "Students"],
    )
    fig.update_layout(height=390, yaxis={"categoryorder": "total ascending"}, margin=dict(l=20, r=20, t=55, b=20))
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


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
    loading_slot = st.empty()
    with loading_slot.container():
        page_header(
            "Loading Dashboard",
            "Preparing Supabase data and applying your access permissions.",
            user["role"],
        )
        st.info("Loading data from Supabase...")

    base_records = store.fetch_base_records(user, results_mode="none")
    page, filters = sidebar_navigation(user, store, base_records)
    if page in ["PSPM ANALYSIS", "DIAGNOSTIC ANALYSIS", "LECTURER PROGRESS", "CLASS PROGRESS", "DOWNLOAD"]:
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
    elif page == "DOWNLOAD":
        download_page(records, user)
    elif page == "DATA MANAGEMENT":
        data_management_page(records, user, store)


if __name__ == "__main__":
    main()
