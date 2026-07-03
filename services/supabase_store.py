from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import streamlit as st
from supabase import Client, create_client


STUDENTS_TABLE = "students"
LECTURERS_TABLE = "lecturers"
PROGRAMS_TABLE = "programs"
RESULTS_TABLE = "results"

STUDENTS_COLUMNS = [
    "id",
    "created_at",
    "NO MATRIK",
    "NAMA PELAJAR",
    "JURUSAN",
    "SISTEM",
    "KELAS",
    "SUBJEK",
    "updated_at",
]
LECTURERS_COLUMNS = ["id", "created_at", "updated_at", "KELAS", "PENSYARAH"]
PROGRAMS_COLUMNS = ["id", "created_at", "updated_at", "NO MATRIK", "PROGRAM"]
RESULTS_COLUMNS = [
    "id",
    "created_at",
    "updated_at",
    "NO MATRIK",
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
SPM_RESULTS_COLUMNS = ["NO MATRIK", "SPM_ADDMATH", "SPM_MATH"]

STUDENTS_WRITABLE_COLUMNS = ["NO MATRIK", "NAMA PELAJAR", "JURUSAN", "SISTEM", "KELAS", "SUBJEK"]
LECTURERS_WRITABLE_COLUMNS = ["KELAS", "PENSYARAH"]
PROGRAMS_WRITABLE_COLUMNS = ["NO MATRIK", "PROGRAM"]
RESULTS_WRITABLE_COLUMNS = [
    "NO MATRIK",
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

UPLOAD_COLUMNS = ["NO MATRIK", "NAMA PELAJAR", "JURUSAN", "SISTEM", "KELAS", "SUBJEK"]


class SupabaseStore:
    def __init__(self) -> None:
        self.client = get_client()
        self.last_errors: list[str] = []

    def sign_out(self) -> None:
        return None

    def refresh_cache(self) -> None:
        clear_cached_reference_data()

    def get_reference_data(self) -> dict[str, pd.DataFrame]:
        refs = self.get_core_reference_data()
        refs["results"] = self.get_results_data()
        return refs

    def get_core_reference_data(self) -> dict[str, pd.DataFrame]:
        refs, errors = get_cached_core_reference_data()
        self.last_errors.extend(errors)
        return {key: value.copy() for key, value in refs.items()}

    def get_results_data(self) -> pd.DataFrame:
        results, errors = get_cached_results_data()
        self.last_errors.extend(errors)
        return results.copy()

    def fetch_records(
        self,
        filters: dict[str, list[str]] | None = None,
        user: dict[str, Any] | None = None,
        results_mode: str = "none",
    ) -> pd.DataFrame:
        records = self.fetch_base_records(user, results_mode=results_mode)
        return self.filter_records(records, filters)

    def fetch_base_records(
        self,
        user: dict[str, Any] | None = None,
        results_mode: str = "none",
    ) -> pd.DataFrame:
        refs = self.get_core_reference_data()
        records = refs["students"].copy()

        if records.empty:
            return records_with_columns(records)

        records = attach_program(records, refs["programs"])
        records = attach_lecturer(records, refs["lecturers"])
        if results_mode == "spm":
            records = attach_results(records, self.get_spm_results_data(), SPM_RESULTS_COLUMNS)
        elif results_mode == "all":
            records = attach_results(records, self.get_results_data(), RESULTS_COLUMNS)

        if user and user.get("role") == "Lecturer":
            records = scope_lecturer_records(records, user)

        return records.sort_values(["NAMA PELAJAR"], ascending=[True], na_position="last")

    def filter_records(
        self,
        records: pd.DataFrame,
        filters: dict[str, list[str]] | None = None,
    ) -> pd.DataFrame:
        records = records.copy()
        filters = filters or {}
        filter_columns = {
            "Pensyarah": "PENSYARAH",
            "Kelas": "KELAS",
            "Subjek": "SUBJEK",
            "Sistem": "SISTEM",
            "Program": "PROGRAM",
            "Jurusan": "JURUSAN",
        }
        for label, column in filter_columns.items():
            values = [value for value in filters.get(label, []) if value]
            if values and column in records and label == "Pensyarah":
                records = records[
                    records[column].apply(
                        lambda cell: any(value in split_multi_value(cell) for value in values)
                    )
                ]
            elif values and column in records:
                records = records[records[column].isin(values)]

        return records.sort_values(["NAMA PELAJAR"], ascending=[True], na_position="last")

    def fetch_filter_options(self, user: dict[str, Any] | None = None) -> dict[str, list[str]]:
        records = self.fetch_base_records(user=user)
        return self.filter_options_from_records(records, user)

    def get_spm_results_data(self) -> pd.DataFrame:
        results, errors = get_cached_spm_results_data()
        self.last_errors.extend(errors)
        return results.copy()

    def filter_options_from_records(
        self,
        records: pd.DataFrame,
        user: dict[str, Any] | None = None,
    ) -> dict[str, list[str]]:
        if user and user.get("role") == "Lecturer" and user.get("PENSYARAH"):
            pensyarah_options = [str(user["PENSYARAH"])]
        else:
            pensyarah_options = sorted(
                {
                    name
                    for value in records.get("PENSYARAH", pd.Series(dtype=str)).dropna()
                    for name in split_multi_value(value)
                }
            )
        return {
            "Pensyarah": pensyarah_options,
            "Kelas": sorted(records.get("KELAS", pd.Series(dtype=str)).dropna().unique().tolist()),
            "Subjek": sorted(records.get("SUBJEK", pd.Series(dtype=str)).dropna().unique().tolist()),
            "Sistem": sorted(records.get("SISTEM", pd.Series(dtype=str)).dropna().unique().tolist()),
            "Program": sorted(records.get("PROGRAM", pd.Series(dtype=str)).dropna().unique().tolist()),
            "Jurusan": sorted(records.get("JURUSAN", pd.Series(dtype=str)).dropna().unique().tolist()),
        }

    def upsert_record(self, payload: dict[str, Any], record_id: Any | None = None) -> None:
        self.upsert_reference("students", payload, record_id)

    def upsert_reference(self, key: str, payload: dict[str, Any], record_id: Any | None = None) -> None:
        table_name, allowed_columns = reference_table_and_columns(key)
        clean = clean_payload(payload, allowed_columns)
        if not clean:
            raise ValueError("No allowed Supabase columns were provided.")
        if record_id:
            self.client.table(table_name).update(clean).eq("id", record_id).execute()
        else:
            self.client.table(table_name).insert(clean).execute()
        clear_cached_reference_data()

    def delete_records(self, record_ids: list[Any]) -> int:
        return self.delete_reference("students", record_ids)

    def delete_reference(self, key: str, record_ids: list[Any]) -> int:
        if not record_ids:
            return 0
        table_name, _ = reference_table_and_columns(key)
        self.client.table(table_name).delete().in_("id", record_ids).execute()
        clear_cached_reference_data()
        return len(record_ids)

    def add_reference(self, key: str, payload: dict[str, Any]) -> None:
        table_name, allowed_columns = reference_table_and_columns(key)
        clean = clean_payload(payload, allowed_columns)
        if not clean:
            raise ValueError("No allowed Supabase columns were provided.")
        self.client.table(table_name).insert(clean).execute()
        clear_cached_reference_data()

    def writable_columns(self, key: str) -> list[str]:
        return reference_table_and_columns(key)[1]

    def bulk_upsert_records(self, df: pd.DataFrame) -> tuple[int, int]:
        saved = self.bulk_upsert_reference("students", df)
        return saved, 0

    def bulk_upsert_reference(self, key: str, df: pd.DataFrame) -> int:
        table_name, allowed_columns = reference_table_and_columns(key)
        current = self.reference_frame(key)
        natural_key = natural_key_column(key)
        saved = 0
        for _, row in df.iterrows():
            raw = row.to_dict()
            payload = clean_payload(raw, allowed_columns)
            if not payload:
                continue
            record_id = raw.get("id")
            if is_empty_value(record_id) and natural_key in payload and natural_key in current:
                matches = current[current[natural_key].astype(str) == str(payload[natural_key])]
                if not matches.empty and "id" in matches:
                    record_id = matches.iloc[0]["id"]
            if is_empty_value(record_id):
                self.client.table(table_name).insert(payload).execute()
            else:
                self.client.table(table_name).update(payload).eq("id", record_id).execute()
            saved += 1
        clear_cached_reference_data()
        return saved

    def reference_frame(self, key: str) -> pd.DataFrame:
        if key == "results":
            return self.get_results_data()
        refs = self.get_core_reference_data()
        return refs.get(key, pd.DataFrame()).copy()

    def _select_table(self, table_name: str, columns: list[str]) -> pd.DataFrame:
        return select_table_frame(self.client, table_name, columns, self.last_errors)


@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured in st.secrets.")
    return create_client(url, key)


@st.cache_data(ttl=600, show_spinner=False)
def get_cached_core_reference_data() -> tuple[dict[str, pd.DataFrame], list[str]]:
    errors: list[str] = []
    client = get_client()
    table_specs = {
        "students": (STUDENTS_TABLE, STUDENTS_COLUMNS),
        "lecturers": (LECTURERS_TABLE, LECTURERS_COLUMNS),
        "programs": (PROGRAMS_TABLE, PROGRAMS_COLUMNS),
    }
    refs: dict[str, pd.DataFrame] = {}

    with ThreadPoolExecutor(max_workers=len(table_specs)) as executor:
        futures = {
            executor.submit(fetch_table_frame, client, table_name, columns): (key, columns)
            for key, (table_name, columns) in table_specs.items()
        }
        for future in as_completed(futures):
            key, columns = futures[future]
            try:
                refs[key], table_errors = future.result()
                errors.extend(table_errors)
            except Exception as exc:
                refs[key] = pd.DataFrame(columns=columns)
                errors.append(f"{key}: {exc}")

    students = refs.get("students", pd.DataFrame(columns=STUDENTS_COLUMNS))
    lecturers = refs.get("lecturers", pd.DataFrame(columns=LECTURERS_COLUMNS))
    programs = refs.get("programs", pd.DataFrame(columns=PROGRAMS_COLUMNS))
    return (
        {
            "students": students,
            "lecturers": lecturers,
            "programs": programs,
            "classes": distinct_frame(students, "KELAS"),
            "subjects": distinct_frame(students, "SUBJEK"),
            "systems": distinct_frame(students, "SISTEM"),
        },
        errors,
    )


@st.cache_data(ttl=600, show_spinner=False)
def get_cached_spm_results_data() -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    results = select_table_frame(get_client(), RESULTS_TABLE, SPM_RESULTS_COLUMNS, errors)
    return results, errors


@st.cache_data(ttl=600, show_spinner=False)
def get_cached_results_data() -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    results = select_table_frame(get_client(), RESULTS_TABLE, RESULTS_COLUMNS, errors)
    return results, errors


def clear_cached_reference_data() -> None:
    get_cached_core_reference_data.clear()
    get_cached_spm_results_data.clear()
    get_cached_results_data.clear()


def fetch_table_frame(
    client: Client,
    table_name: str,
    columns: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    return select_table_frame(client, table_name, columns, errors), errors


def select_table_frame(
    client: Client,
    table_name: str,
    columns: list[str],
    errors: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    page_size = 1000
    start = 0
    try:
        while True:
            response = (
                client.table(table_name)
                .select(select_columns(columns))
                .range(start, start + page_size - 1)
                .execute()
            )
            page = response.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            start += page_size
        return pd.DataFrame(rows, columns=columns)
    except Exception as exc:
        errors.append(f"{table_name}: {exc}")
        return pd.DataFrame(columns=columns)


def attach_program(students: pd.DataFrame, programs: pd.DataFrame) -> pd.DataFrame:
    if programs.empty:
        students["PROGRAM"] = None
        return students
    program_lookup = first_non_empty_by_key(programs, "NO MATRIK", "PROGRAM")
    students["PROGRAM"] = students["NO MATRIK"].map(program_lookup).fillna(students["JURUSAN"])
    return students


def attach_lecturer(students: pd.DataFrame, lecturers: pd.DataFrame) -> pd.DataFrame:
    if lecturers.empty:
        students["PENSYARAH"] = None
        return students
    lecturer_lookup = first_non_empty_by_key(lecturers, "KELAS", "PENSYARAH")
    students["PENSYARAH"] = students["KELAS"].map(lecturer_lookup)
    return students


def attach_results(
    students: pd.DataFrame,
    results: pd.DataFrame,
    result_columns: list[str],
) -> pd.DataFrame:
    display_columns = [column for column in result_columns if column not in ["id", "created_at", "updated_at", "NO MATRIK"]]
    if results.empty:
        for column in display_columns:
            if column not in students:
                students[column] = None
        return students

    merge_columns = [column for column in result_columns if column not in ["id", "created_at", "updated_at"]]
    compact_results = (
        results[merge_columns]
        .replace("", pd.NA)
        .dropna(subset=["NO MATRIK"])
        .groupby("NO MATRIK", as_index=False)
        .first()
    )
    merged = students.merge(compact_results, on="NO MATRIK", how="left")
    for column in display_columns:
        if column not in merged:
            merged[column] = None
    return merged


def records_with_columns(records: pd.DataFrame) -> pd.DataFrame:
    result_display_columns = [column for column in RESULTS_COLUMNS if column not in ["id", "created_at", "updated_at", "NO MATRIK"]]
    for column in [*STUDENTS_COLUMNS, "PROGRAM", "PENSYARAH", *result_display_columns]:
        if column not in records:
            records[column] = pd.Series(dtype="object")
    return records


def distinct_frame(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty or column not in df:
        return pd.DataFrame(columns=[column])
    values = sorted(value for value in df[column].dropna().unique().tolist() if value != "")
    return pd.DataFrame({column: values})


def clean_payload(payload: dict[str, Any], allowed_columns: list[str]) -> dict[str, Any]:
    return {
        column: payload[column]
        for column in allowed_columns
        if column in payload and not is_empty_value(payload[column])
    }


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def first_non_empty(values: pd.Series) -> Any:
    non_empty = values.dropna()
    non_empty = non_empty[non_empty.astype(str).str.strip() != ""]
    return non_empty.iloc[0] if not non_empty.empty else None


def first_non_empty_by_key(df: pd.DataFrame, key_column: str, value_column: str) -> dict[Any, Any]:
    compact = (
        df[[key_column, value_column]]
        .replace("", pd.NA)
        .dropna(subset=[key_column])
        .groupby(key_column, as_index=False)[value_column]
        .first()
    )
    return compact.set_index(key_column)[value_column].dropna().to_dict()


def unique_non_empty_join(values: pd.Series) -> str | None:
    seen: list[str] = []
    for value in values.dropna():
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return ", ".join(seen) if seen else None


def unique_non_empty_by_key(df: pd.DataFrame, key_column: str, value_column: str) -> dict[Any, Any]:
    compact = (
        df[[key_column, value_column]]
        .dropna(subset=[key_column])
        .groupby(key_column, as_index=False)[value_column]
        .agg(unique_non_empty_join)
    )
    return compact.set_index(key_column)[value_column].dropna().to_dict()


def split_multi_value(value: Any) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def select_columns(columns: list[str]) -> str:
    return ",".join(f'"{column}"' if " " in column else column for column in columns)


def reference_table_and_columns(key: str) -> tuple[str, list[str]]:
    if key == "students":
        return STUDENTS_TABLE, STUDENTS_WRITABLE_COLUMNS
    if key == "lecturers":
        return LECTURERS_TABLE, LECTURERS_WRITABLE_COLUMNS
    if key == "programs":
        return PROGRAMS_TABLE, PROGRAMS_WRITABLE_COLUMNS
    if key == "results":
        return RESULTS_TABLE, RESULTS_WRITABLE_COLUMNS
    raise ValueError("Only existing Supabase tables can be edited: students, lecturers, programs, results.")


def natural_key_column(key: str) -> str:
    if key in ["students", "programs", "results"]:
        return "NO MATRIK"
    if key == "lecturers":
        return "KELAS"
    raise ValueError("Only existing Supabase tables can be edited: students, lecturers, programs, results.")


def scope_lecturer_records(records: pd.DataFrame, user: dict[str, Any]) -> pd.DataFrame:
    pensyarah_value = user.get("PENSYARAH")
    if pensyarah_value and "PENSYARAH" in records:
        lecturer_name = str(pensyarah_value).strip().lower()
        match = records["PENSYARAH"].apply(
            lambda cell: lecturer_name in [name.lower() for name in split_multi_value(cell)]
        )
        if match.any():
            return records[match]
    return records.iloc[0:0]


def validate_import_frame(
    raw: pd.DataFrame,
    refs: dict[str, pd.DataFrame],
    dataset_key: str = "students",
) -> tuple[pd.DataFrame, list[str]]:
    df = raw.copy()
    template_columns = create_upload_template(dataset_key).columns.tolist()
    writable_columns = reference_table_and_columns(dataset_key)[1]
    import_columns = [column for column in template_columns if column in df.columns]
    missing = [column for column in writable_columns if column not in df.columns]
    errors = [f"Missing column: {column}" for column in missing]
    if errors:
        return df, errors

    df = df[import_columns].copy()
    for column in df.columns:
        df[column] = df[column].fillna("").astype(str).str.strip()

    required = required_import_columns(dataset_key)
    for row_number, row in df.iterrows():
        for column in required:
            if row[column] == "":
                errors.append(f"Row {row_number + 2}: {column} is required")
        if dataset_key == "results":
            result_values = [row[column] for column in RESULTS_WRITABLE_COLUMNS if column != "NO MATRIK"]
            if not any(value != "" for value in result_values):
                errors.append(f"Row {row_number + 2}: at least one result column is required")

    return df, errors


def required_import_columns(dataset_key: str) -> list[str]:
    required = {
        "students": ["NO MATRIK", "NAMA PELAJAR", "KELAS", "SUBJEK"],
        "lecturers": ["KELAS", "PENSYARAH"],
        "programs": ["NO MATRIK", "PROGRAM"],
        "results": ["NO MATRIK"],
    }
    return required[dataset_key]


def create_upload_template(dataset_key: str = "students") -> pd.DataFrame:
    _, writable_columns = reference_table_and_columns(dataset_key)
    return pd.DataFrame(columns=["id", *writable_columns])
