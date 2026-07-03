from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from components.ui import afj_sidebar_brand, app_brand, blank_state, inject_theme, page_header
from services.supabase_store import (
    create_upload_template,
    SupabaseStore,
    validate_import_frame,
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
    "A": 100,
    "A-": 90,
    "B+": 85,
    "B": 80,
    "B-": 75,
    "C+": 70,
    "C": 65,
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
            "DIAGNOSTIC ANALYSIS",
            "LECTURER & CLASS PERFORMANCE",
            "DATA MANAGEMENT",
        ],
        "Executive": [
            "DEMOGRAPHY",
            "SPM ANALYSIS",
            "DIAGNOSTIC ANALYSIS",
            "LECTURER & CLASS PERFORMANCE",
        ],
        "Lecturer": [
            "DEMOGRAPHY",
            "SPM ANALYSIS",
            "DIAGNOSTIC ANALYSIS",
            "LECTURER & CLASS PERFORMANCE",
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

    demography_export = filtered_columns(
        records,
        [
            "NO MATRIK",
            "NAMA PELAJAR",
            "JURUSAN",
            "SISTEM",
            "KELAS",
            "SUBJEK",
            "PROGRAM",
            "PENSYARAH",
        ],
    )
    render_download_buttons(demography_export, "demography_filtered_data", "Filtered Demography Data")

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

    spm_export = filtered_columns(
        spm_records,
        [
            "NO MATRIK",
            "NAMA PELAJAR",
            "KELAS",
            "SUBJEK",
            "PENSYARAH",
            *selected_spm_columns,
        ],
    )
    render_download_buttons(spm_export, "spm_analysis_filtered_data", "Filtered SPM Analysis Data")

    kpis = st.columns(4)
    kpis[0].metric("SPM Math Records", f"{spm_records['SPM_MATH'].notna().sum():,}" if "SPM_MATH" in spm_records else "0")
    kpis[1].metric("SPM Add Math Records", f"{spm_records['SPM_ADDMATH'].notna().sum():,}" if "SPM_ADDMATH" in spm_records else "0")
    kpis[2].metric("SPM Math Grades", f"{spm_records['SPM_MATH'].nunique():,}" if "SPM_MATH" in spm_records else "0")
    kpis[3].metric("SPM Add Math Grades", f"{spm_records['SPM_ADDMATH'].nunique():,}" if "SPM_ADDMATH" in spm_records else "0")

    grade_long = pd.concat(
        [
            spm_records[[column]].rename(columns={column: "GRADE"}).assign(RESULT=column)
            for column in selected_spm_columns
        ],
        ignore_index=True,
    ).dropna()
    grade_counts = grade_long.value_counts(["RESULT", "GRADE"]).reset_index(name="COUNT")

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
        comparison = grade_counts.groupby("RESULT", as_index=False)["COUNT"].sum()
        fig = px.pie(
            comparison,
            names="RESULT",
            values="COUNT",
            hole=0.48,
            title="Mathematics vs Additional Mathematics Result Volume",
            color_discrete_sequence=["#1d4ed8", "#0f766e"],
        )
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        proportions = grade_counts.copy()
        totals = proportions.groupby("RESULT")["COUNT"].transform("sum")
        proportions["PERCENT"] = proportions["COUNT"] / totals * 100
        fig = px.bar(
            proportions,
            x="RESULT",
            y="PERCENT",
            color="GRADE",
            title="Grade Proportion",
            category_orders={"GRADE": GRADE_ORDER},
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_layout(height=360, yaxis_title="Percent", margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        available_result_columns = [column for column in RESULT_COLUMNS if column in spm_records]
        result_completeness = (
            spm_records[available_result_columns]
            .notna()
            .sum()
            .rename_axis("RESULT_COLUMN")
            .reset_index(name="COUNT")
        )
        fig = px.line(
            result_completeness,
            x="RESULT_COLUMN",
            y="COUNT",
            markers=True,
            title="Available Result Columns",
            color_discrete_sequence=["#1d4ed8"],
        )
        fig.update_layout(height=360, xaxis_title="", margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("SPM Grade Matrix")
    if {"SPM_MATH", "SPM_ADDMATH"}.issubset(selected_spm_columns):
        matrix = pd.crosstab(spm_records["SPM_MATH"], spm_records["SPM_ADDMATH"])
        matrix = matrix.reindex(index=GRADE_ORDER, columns=GRADE_ORDER, fill_value=0).dropna(how="all")
        st.dataframe(matrix, use_container_width=True)
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

    diagnostic_export = filtered_columns(
        records,
        [
            "NO MATRIK",
            "NAMA PELAJAR",
            "KELAS",
            "PENSYARAH",
            "JURUSAN",
            "PROGRAM",
            *diagnostic_columns,
        ],
    )
    render_download_buttons(diagnostic_export, "diagnostic_analysis_filtered_data", "Filtered Diagnostic Analysis Data")

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
        top_classes = (
            class_progress[class_progress["Test"] == latest_test]
            .sort_values("Score", ascending=False)
            .head(8)["KELAS"]
            .tolist()
        )
        fig = px.line(
            class_progress[class_progress["KELAS"].isin(top_classes)],
            x="Test",
            y="Score",
            color="KELAS",
            markers=True,
            title="Top Class Progress",
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
        lecturer_average = (
            diagnostic_long.groupby("PENSYARAH", as_index=False)["Score"]
            .mean()
            .sort_values("Score", ascending=False)
            .head(12)
        )
        fig = px.bar(
            lecturer_average,
            x="Score",
            y="PENSYARAH",
            orientation="h",
            title="Average AMAT by Lecturer",
            color="Score",
            color_continuous_scale="Teal",
        )
        fig.update_layout(height=360, yaxis={"categoryorder": "total ascending"}, margin=dict(l=20, r=20, t=55, b=20))
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


def lecturer_class_performance_page(records: pd.DataFrame, user: dict, filters: dict[str, list[str]]) -> None:
    page_header(
        "LECTURER & CLASS PERFORMANCE",
        "Rank lecturers and classes across PSPM and AMAT assessments.",
        user["role"],
    )
    performance_columns = selected_ujian_columns(filters, PERFORMANCE_COLUMNS)
    if not performance_columns:
        blank_state("The selected Ujian filter does not include PSPM or AMAT assessments.")
        return
    performance_long = assessment_long_frame(records, performance_columns)
    if performance_long.empty:
        blank_state("No assessment data match the selected filters.")
        return

    render_download_buttons(
        performance_long,
        "lecturer_class_performance_filtered_data",
        "Filtered Lecturer and Class Performance Data",
    )

    kpis = st.columns(4)
    kpis[0].metric("Students", f"{performance_long['NO MATRIK'].nunique():,}")
    kpis[1].metric("Assessments", f"{performance_long['Test'].nunique():,}")
    kpis[2].metric("Overall Score", f"{performance_long['Score'].mean():.1f}")
    kpis[3].metric("Classes", f"{performance_long['KELAS'].nunique():,}")

    lecturer_rank = ranked_performance(performance_long, "PENSYARAH")
    class_rank = ranked_performance(performance_long, "KELAS")

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            lecturer_rank.head(15),
            x="Average Score",
            y="PENSYARAH",
            orientation="h",
            title="Lecturer Ranking",
            color="Average Score",
            color_continuous_scale="Teal",
        )
        fig.update_layout(height=430, yaxis={"categoryorder": "total ascending"}, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        fig = px.bar(
            class_rank.head(15),
            x="Average Score",
            y="KELAS",
            orientation="h",
            title="Class Ranking",
            color="Average Score",
            color_continuous_scale="Blues",
        )
        fig.update_layout(height=430, yaxis={"categoryorder": "total ascending"}, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        lecturer_heatmap = performance_long.pivot_table(
            index="PENSYARAH",
            columns="Test",
            values="Score",
            aggfunc="mean",
        ).reindex(columns=performance_columns)
        fig = px.imshow(
            lecturer_heatmap,
            aspect="auto",
            color_continuous_scale="YlGnBu",
            title="Lecturer Performance by Assessment",
        )
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        test_average = performance_long.groupby("Test", as_index=False)["Score"].mean()
        fig = px.line(
            test_average,
            x="Test",
            y="Score",
            markers=True,
            title="Overall Assessment Trend",
            category_orders={"Test": performance_columns},
            color_discrete_sequence=["#1d4ed8"],
        )
        fig.update_layout(height=390, yaxis_range=[0, 100], margin=dict(l=20, r=20, t=55, b=20))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Lecturer Ranking Table")
    st.dataframe(lecturer_rank, hide_index=True, use_container_width=True)
    st.subheader("Class Ranking Table")
    st.dataframe(class_rank, hide_index=True, use_container_width=True)


def data_management_page(records: pd.DataFrame, user: dict, store: SupabaseStore) -> None:
    page_header(
        "DATA MANAGEMENT",
        "Create, update, delete, import, and validate academic records.",
        user["role"],
    )
    if user["role"] != "Admin":
        st.error("You do not have permission to access DATA MANAGEMENT.")
        return

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
            st.success(f"Deleted {deleted} record(s).")
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
                st.success("Record saved successfully.")
                st.rerun()

    with tab_import:
        st.subheader(f"Bulk Import and Update {dataset_label}")
        st.caption("Upload CSV or Excel files using only the exact Supabase columns. Include id to update a specific row, or use the natural key to update the first matching row.")
        template = create_upload_template(dataset_key)
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
                preview, errors = validate_import_frame(incoming, refs, dataset_key)
                st.subheader("Preview")
                st.dataframe(preview, hide_index=True, use_container_width=True)
                if errors:
                    st.error("Please fix the validation errors before saving.")
                    st.write(errors)
                elif st.button("Save imported data", type="primary"):
                    saved = store.bulk_upsert_reference(dataset_key, preview)
                    st.success(f"Import complete. {saved} {dataset_label.lower()} record(s) saved.")
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
    if "PENSYARAH" in combined:
        combined = combined[combined["PENSYARAH"].fillna("").astype(str).str.strip() != ""]
    return combined


def ranked_performance(performance_long: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if performance_long.empty or group_column not in performance_long:
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
    if page in ["DIAGNOSTIC ANALYSIS", "LECTURER & CLASS PERFORMANCE"]:
        base_records = store.fetch_base_records(user, results_mode="all")
    elif page in ["SPM ANALYSIS", "DATA MANAGEMENT"]:
        base_records = store.fetch_base_records(user, results_mode="spm")
    records = store.filter_records(base_records, filters)
    loading_slot.empty()

    if page == "DEMOGRAPHY":
        demography_dashboard(records, user)
    elif page == "SPM ANALYSIS":
        results_dashboard(records, user, filters)
    elif page == "DIAGNOSTIC ANALYSIS":
        diagnostic_dashboard(records, user, filters)
    elif page == "LECTURER & CLASS PERFORMANCE":
        lecturer_class_performance_page(records, user, filters)
    elif page == "DATA MANAGEMENT":
        data_management_page(records, user, store)


if __name__ == "__main__":
    main()
