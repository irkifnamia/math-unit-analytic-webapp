from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from time import sleep
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd
import streamlit as st
from supabase import Client, create_client


STUDENTS_TABLE = "students"
LECTURERS_TABLE = "lecturers"
PROGRAMS_TABLE = "programs"
RESULTS_TABLE = "results"
ASSESSMENTS_TABLE = "assessments"
EDIT_HISTORY_TABLE = "edit_history"
APP_USERS_TABLE = "app_users"
UPLOAD_ROW_NUMBER_COLUMN = "_UPLOAD_ROW_NUMBER"

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
ASSESSMENTS_COLUMNS = ["id", "created_at", "updated_at", "UJIAN", "KATEGORI", "SUBJEK"]
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
ASSESSMENTS_WRITABLE_COLUMNS = ["UJIAN", "KATEGORI", "SUBJEK"]
EDIT_HISTORY_COLUMNS = [
    "id",
    "created_at",
    "source",
    "user_id",
    "user_name",
    "user_role",
    "action",
    "dataset",
    "record_id",
    "details",
    "old_data",
    "new_data",
]
EDIT_HISTORY_FALLBACK_COLUMNS = [
    "id",
    "created_at",
    "user_id",
    "user_name",
    "user_role",
    "action",
    "dataset",
    "record_id",
    "details",
]
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

UPLOAD_COLUMNS = ["NO MATRIK", "NAMA PELAJAR", "JURUSAN", "SISTEM", "KELAS", "SUBJEK"]


class BulkImportBatchError(RuntimeError):
    def __init__(
        self,
        batch_number: int,
        total_batches: int,
        row_numbers: list[int],
        original_error: Exception,
    ) -> None:
        self.batch_number = batch_number
        self.total_batches = total_batches
        self.row_numbers = row_numbers
        self.original_error = original_error
        super().__init__(
            f"Batch {batch_number} of {total_batches} failed for uploaded row(s) "
            f"{format_row_number_list(row_numbers)}. Supabase error: {original_error}"
        )


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
        refs["assessments"] = self.get_assessments_data()
        return refs

    def get_core_reference_data(self) -> dict[str, pd.DataFrame]:
        refs, errors = get_cached_core_reference_data()
        self.last_errors.extend(errors)
        return {key: value.copy() for key, value in refs.items()}

    def get_results_data(self) -> pd.DataFrame:
        results, errors = get_cached_results_data()
        self.last_errors.extend(errors)
        return results.copy()

    def get_assessments_data(self) -> pd.DataFrame:
        assessments, errors = get_cached_assessments_data()
        self.last_errors.extend(errors)
        return assessments.copy()

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
            all_results = self.get_results_data()
            records = attach_results(records, all_results, all_results.columns.tolist() or RESULTS_COLUMNS)

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
        pensyarah_options = sorted(
            {
                name
                for value in records.get("PENSYARAH", pd.Series(dtype=str)).dropna()
                for name in split_multi_value(value)
            }
        )
        jurusan_values = {
            comparable_label(value)
            for value in records.get("JURUSAN", pd.Series(dtype=str)).dropna().unique().tolist()
            if comparable_label(value)
        }
        program_options = sorted(
            value
            for value in records.get("PROGRAM", pd.Series(dtype=str)).dropna().unique().tolist()
            if not is_jurusan_program_value(value, jurusan_values)
        )
        return {
            "Pensyarah": pensyarah_options,
            "Kelas": sorted(records.get("KELAS", pd.Series(dtype=str)).dropna().unique().tolist()),
            "Subjek": sorted(records.get("SUBJEK", pd.Series(dtype=str)).dropna().unique().tolist()),
            "Sistem": sorted(records.get("SISTEM", pd.Series(dtype=str)).dropna().unique().tolist()),
            "Program": program_options,
            "Jurusan": sorted(records.get("JURUSAN", pd.Series(dtype=str)).dropna().unique().tolist()),
        }

    def upsert_record(self, payload: dict[str, Any], record_id: Any | None = None) -> None:
        self.upsert_reference("students", payload, record_id)

    def upsert_reference(self, key: str, payload: dict[str, Any], record_id: Any | None = None) -> None:
        table_name, allowed_columns = self.reference_table_and_columns(key)
        clean = clean_payload(payload, allowed_columns, include_empty=bool(record_id))
        if not clean:
            raise ValueError("No allowed Supabase columns were provided.")
        record_id = normalize_supabase_id(record_id)
        clean = with_updated_at(clean, table_name)
        if not is_empty_value(record_id):
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
        record_ids = [record_id for record_id in (normalize_supabase_id(value) for value in record_ids) if not is_empty_value(record_id)]
        if not record_ids:
            return 0
        self.client.table(table_name).delete().in_("id", record_ids).execute()
        clear_cached_reference_data()
        return len(record_ids)

    def add_reference(self, key: str, payload: dict[str, Any]) -> None:
        table_name, allowed_columns = self.reference_table_and_columns(key)
        clean = clean_payload(payload, allowed_columns)
        if not clean:
            raise ValueError("No allowed Supabase columns were provided.")
        self.client.table(table_name).insert(clean).execute()
        clear_cached_reference_data()

    def writable_columns(self, key: str) -> list[str]:
        return self.reference_table_and_columns(key)[1]

    def reference_table_and_columns(self, key: str) -> tuple[str, list[str]]:
        if key == "results":
            results = self.get_results_data()
            if not results.empty:
                columns = [
                    column
                    for column in results.columns.tolist()
                    if column not in ["id", "created_at", "updated_at"]
                ]
                columns = unique_columns(columns)
                if "NO MATRIK" in columns:
                    columns = ["NO MATRIK", *[column for column in columns if column != "NO MATRIK"]]
                return RESULTS_TABLE, columns
        if key == "assessments":
            assessments = self.get_assessments_data()
            if not assessments.empty:
                columns = [
                    column
                    for column in assessments.columns.tolist()
                    if column not in ["id", "created_at", "updated_at"]
                ]
                columns = unique_columns(columns)
                ordered = [column for column in ASSESSMENTS_WRITABLE_COLUMNS if column in columns]
                extras = [column for column in columns if column not in ordered]
                return ASSESSMENTS_TABLE, [*ordered, *extras]
        return reference_table_and_columns(key)

    def bulk_upsert_records(self, df: pd.DataFrame) -> tuple[int, int]:
        saved = self.bulk_upsert_reference("students", df)
        return saved, 0

    def bulk_upsert_reference(
        self,
        key: str,
        df: pd.DataFrame,
        match_column: str | None = None,
        batch_size: int = 200,
        progress_callback: Callable[[int, int, int, int, list[int]], None] | None = None,
    ) -> int:
        table_name, allowed_columns = self.reference_table_and_columns(key)
        match_column = match_column or natural_key_column(key)
        rows: list[dict[str, Any]] = []
        for _, row in df.iterrows():
            raw = row.to_dict()
            payload = clean_payload(raw, allowed_columns, include_empty=True)
            if not payload:
                continue
            write_payload = with_updated_at(payload, table_name)
            if match_column == "id":
                record_id = normalize_supabase_id(raw.get("id"))
                if not is_empty_value(record_id):
                    write_payload["id"] = record_id
            else:
                match_value = raw.get(match_column)
                if is_empty_value(match_value):
                    continue
                write_payload[match_column] = match_value
            if UPLOAD_ROW_NUMBER_COLUMN in raw:
                write_payload[UPLOAD_ROW_NUMBER_COLUMN] = raw.get(UPLOAD_ROW_NUMBER_COLUMN)
            rows.append(write_payload)

        if not rows:
            return 0

        saved = bulk_upsert_batches(
            self.client,
            table_name,
            rows,
            match_column,
            batch_size=batch_size,
            progress_callback=progress_callback,
        )
        clear_cached_reference_data()
        return saved

    def reference_frame(self, key: str) -> pd.DataFrame:
        if key == "results":
            return self.get_results_data()
        refs = self.get_core_reference_data()
        return refs.get(key, pd.DataFrame()).copy()

    def get_edit_history(self) -> pd.DataFrame:
        errors: list[str] = []
        history = select_table_frame(self.client, EDIT_HISTORY_TABLE, EDIT_HISTORY_COLUMNS, errors)
        if errors:
            fallback_errors: list[str] = []
            history = select_table_frame(
                self.client,
                EDIT_HISTORY_TABLE,
                EDIT_HISTORY_FALLBACK_COLUMNS,
                fallback_errors,
            )
            if not history.empty and "source" not in history:
                history["source"] = "APP"
            self.last_errors.extend(fallback_errors or errors)
        else:
            self.last_errors.extend(errors)
        if history.empty:
            return history
        return history.sort_values("created_at", ascending=False, na_position="last")

    def log_edit_history(
        self,
        user: dict[str, Any],
        action: str,
        dataset: str,
        record_id: Any | None = None,
        details: str | None = None,
    ) -> bool:
        payload = {
            "source": "APP",
            "user_id": user.get("id") or user.get("ic_number"),
            "user_name": user.get("full_name"),
            "user_role": user.get("role"),
            "action": action,
            "dataset": dataset,
            "record_id": None if is_empty_value(record_id) else str(record_id),
            "details": details,
        }
        try:
            self.client.table(EDIT_HISTORY_TABLE).insert(payload).execute()
            return True
        except Exception as exc:
            try:
                legacy_payload = {
                    key: value
                    for key, value in payload.items()
                    if key in EDIT_HISTORY_FALLBACK_COLUMNS and key not in ["id", "created_at"]
                }
                self.client.table(EDIT_HISTORY_TABLE).insert(legacy_payload).execute()
                return True
            except Exception:
                self.last_errors.append(f"Edit history logging skipped: {exc}")
                return False

    def get_app_users(self) -> pd.DataFrame:
        errors: list[str] = []
        users = select_table_frame(self.client, APP_USERS_TABLE, APP_USERS_COLUMNS, errors)
        self.last_errors.extend(errors)
        if users.empty:
            return users
        return users.sort_values(["role", "full_name"], ascending=[True, True], na_position="last")

    def upsert_app_user(self, payload: dict[str, Any], record_id: Any | None = None) -> None:
        allowed_columns = ["ic_number", "full_name", "role", "pensyarah", "is_active"]
        clean = clean_payload(payload, allowed_columns)
        if "ic_number" in clean:
            clean["ic_number"] = "".join(character for character in str(clean["ic_number"]) if character.isdigit())
        if "role" in clean:
            clean["role"] = str(clean["role"] or "lecturer").strip().lower()
        if "is_active" not in clean:
            clean["is_active"] = True
        if not clean.get("ic_number") or not clean.get("full_name") or not clean.get("role"):
            raise ValueError("IC number, user name, and role are required.")
        record_id = normalize_supabase_id(record_id)
        clean = with_updated_at(clean, APP_USERS_TABLE)
        if not is_empty_value(record_id):
            self.client.table(APP_USERS_TABLE).update(clean).eq("id", record_id).execute()
        else:
            self.client.table(APP_USERS_TABLE).upsert(clean, on_conflict="ic_number").execute()

    def delete_app_users(self, record_ids: list[Any]) -> int:
        if not record_ids:
            return 0
        record_ids = [record_id for record_id in (normalize_supabase_id(value) for value in record_ids) if not is_empty_value(record_id)]
        if not record_ids:
            return 0
        self.client.table(APP_USERS_TABLE).delete().in_("id", record_ids).execute()
        return len(record_ids)

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
    results = select_all_table_frame(get_client(), RESULTS_TABLE, errors, fallback_columns=RESULTS_COLUMNS)
    return results, errors


@st.cache_data(ttl=600, show_spinner=False)
def get_cached_assessments_data() -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []
    assessments = select_all_table_frame(get_client(), ASSESSMENTS_TABLE, errors, fallback_columns=ASSESSMENTS_COLUMNS)
    return assessments, errors


def clear_cached_reference_data() -> None:
    get_cached_core_reference_data.clear()
    get_cached_spm_results_data.clear()
    get_cached_results_data.clear()
    get_cached_assessments_data.clear()


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


def select_all_table_frame(
    client: Client,
    table_name: str,
    errors: list[str],
    fallback_columns: list[str] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    page_size = 1000
    start = 0
    try:
        while True:
            response = client.table(table_name).select("*").range(start, start + page_size - 1).execute()
            page = response.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            start += page_size
        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame(columns=fallback_columns or [])
    except Exception as exc:
        errors.append(f"{table_name}: {exc}")
        return pd.DataFrame(columns=fallback_columns or [])


def comparable_label(value: Any) -> str:
    return " ".join(str(value).replace("–", "-").replace("—", "-").split()).casefold()


def is_jurusan_program_value(value: Any, jurusan_values: set[str]) -> bool:
    normalized = comparable_label(value)
    if not normalized:
        return False
    return (
        normalized in jurusan_values
        or "modul" in normalized
        or normalized in {"perakaunan", "sains komputer"}
    )


def attach_program(students: pd.DataFrame, programs: pd.DataFrame) -> pd.DataFrame:
    if programs.empty:
        students["PROGRAM"] = None
        return students
    program_lookup = first_non_empty_by_key(programs, "NO MATRIK", "PROGRAM")
    students["PROGRAM"] = students["NO MATRIK"].map(program_lookup)
    students["PROGRAM"] = students["PROGRAM"].replace("", pd.NA)
    if "JURUSAN" in students:
        jurusan_values = {
            comparable_label(value)
            for value in students["JURUSAN"].dropna().unique().tolist()
            if comparable_label(value)
        }
        if jurusan_values:
            mixed_jurusan = students["PROGRAM"].apply(lambda value: is_jurusan_program_value(value, jurusan_values))
            students.loc[mixed_jurusan.fillna(False), "PROGRAM"] = pd.NA
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


def clean_payload(
    payload: dict[str, Any],
    allowed_columns: list[str],
    include_empty: bool = False,
) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for column in allowed_columns:
        if column not in payload:
            continue
        value = payload[column]
        if is_empty_value(value):
            if include_empty:
                clean[column] = None
            continue
        if is_whole_number_result_column(column):
            value = normalize_whole_number(value, column)
        clean[column] = value
    return clean


def is_whole_number_result_column(column: str) -> bool:
    normalized = str(column).upper().strip()
    return normalized.startswith(("AMAT", "TOP", "EVSM", "EVDM"))


def normalize_whole_number(value: Any, column: str) -> int:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        raise ValueError(f"{column} must be a whole number.")
    if not float(number).is_integer():
        raise ValueError(f"{column} must be a whole number.")
    return int(number)


def with_updated_at(payload: dict[str, Any], table_name: str) -> dict[str, Any]:
    timestamp_tables = {
        STUDENTS_TABLE,
        LECTURERS_TABLE,
        PROGRAMS_TABLE,
        RESULTS_TABLE,
        ASSESSMENTS_TABLE,
        APP_USERS_TABLE,
    }
    if table_name not in timestamp_tables:
        return payload
    stamped = payload.copy()
    stamped["updated_at"] = datetime.now(timezone.utc).isoformat()
    return stamped


def bulk_upsert_batches(
    client: Client,
    table_name: str,
    rows: list[dict[str, Any]],
    match_column: str,
    batch_size: int = 200,
    progress_callback: Callable[[int, int, int, int, list[int]], None] | None = None,
) -> int:
    saved = 0
    total_rows = len(rows)
    total_batches = max(1, (total_rows + batch_size - 1) // batch_size)
    for start in range(0, len(rows), batch_size):
        batch_number = start // batch_size + 1
        batch = rows[start : start + batch_size]
        row_numbers = batch_upload_row_numbers(batch, start)
        write_batch = strip_internal_bulk_columns(batch)
        try:
            saved += upsert_batch_adaptive(
                client,
                table_name,
                write_batch,
                match_column,
            )
        except Exception as exc:
            raise BulkImportBatchError(batch_number, total_batches, row_numbers, exc) from exc
        if progress_callback:
            progress_callback(batch_number, total_batches, saved, total_rows, row_numbers)
    return saved


def strip_internal_bulk_columns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {column: value for column, value in row.items() if column != UPLOAD_ROW_NUMBER_COLUMN}
        for row in rows
    ]


def batch_upload_row_numbers(rows: list[dict[str, Any]], start_index: int) -> list[int]:
    row_numbers: list[int] = []
    for offset, row in enumerate(rows):
        value = row.get(UPLOAD_ROW_NUMBER_COLUMN)
        try:
            row_numbers.append(int(value))
        except (TypeError, ValueError):
            row_numbers.append(start_index + offset + 2)
    return row_numbers


def format_row_number_list(row_numbers: list[int]) -> str:
    if not row_numbers:
        return "unknown"
    if len(row_numbers) <= 12:
        return ", ".join(str(number) for number in row_numbers)
    return f"{row_numbers[0]}-{row_numbers[-1]} ({len(row_numbers)} rows)"


def bulk_sync_by_match_column(
    client: Client,
    table_name: str,
    rows: list[dict[str, Any]],
    match_column: str,
) -> int:
    existing_values = existing_match_values(client, table_name, match_column)
    update_rows: list[dict[str, Any]] = []
    insert_rows: list[dict[str, Any]] = []
    for row in rows:
        match_value = row.get(match_column)
        if is_empty_value(match_value):
            continue
        if match_lookup_key(match_value) in existing_values:
            update_rows.append(row)
        else:
            insert_rows.append(row)

    saved = 0
    if update_rows:
        saved += bulk_update_rows_by_match(client, table_name, update_rows, match_column)
    if insert_rows:
        saved += bulk_insert_batches(client, table_name, insert_rows)
    return saved


def existing_match_values(client: Client, table_name: str, match_column: str) -> set[str]:
    errors: list[str] = []
    frame = select_table_frame(client, table_name, [match_column], errors)
    if errors:
        raise RuntimeError("; ".join(errors))
    if frame.empty or match_column not in frame:
        return set()
    return {match_lookup_key(value) for value in frame[match_column].tolist() if not is_empty_value(value)}


def match_lookup_key(value: Any) -> str:
    return str(value).strip()


def bulk_update_rows_by_match(
    client: Client,
    table_name: str,
    rows: list[dict[str, Any]],
    match_column: str,
) -> int:
    grouped: dict[str, dict[str, Any]] = {}
    bulk_timestamp = datetime.now(timezone.utc).isoformat()
    for row in rows:
        match_value = row.get(match_column)
        if is_empty_value(match_value):
            continue
        payload = {
            column: value
            for column, value in row.items()
            if column not in {match_column, "id", "updated_at"}
        }
        if "updated_at" in row:
            payload["updated_at"] = bulk_timestamp
        if not payload:
            continue
        signature = json.dumps(payload, sort_keys=True, default=str)
        if signature not in grouped:
            grouped[signature] = {"payload": payload, "match_values": []}
        grouped[signature]["match_values"].append(match_value)

    saved = 0
    for group in grouped.values():
        payload = group["payload"]
        match_values = group["match_values"]
        for start in range(0, len(match_values), 25):
            chunk = match_values[start : start + 25]
            execute_update_in_adaptive(client, table_name, payload, match_column, chunk)
            saved += len(chunk)
    return saved


def bulk_insert_batches(client: Client, table_name: str, rows: list[dict[str, Any]]) -> int:
    saved = 0
    batch_size = 20
    for start in range(0, len(rows), batch_size):
        saved += insert_batch_adaptive(client, table_name, rows[start : start + batch_size])
    return saved


def insert_batch_adaptive(client: Client, table_name: str, batch: list[dict[str, Any]]) -> int:
    if not batch:
        return 0
    try:
        execute_insert_batch(client, table_name, batch)
        return len(batch)
    except Exception as exc:
        if len(batch) == 1 or not is_transient_disconnect(exc):
            raise
        midpoint = len(batch) // 2
        sleep(0.5)
        return insert_batch_adaptive(client, table_name, batch[:midpoint]) + insert_batch_adaptive(
            client,
            table_name,
            batch[midpoint:],
        )


def execute_insert_batch(client: Client, table_name: str, batch: list[dict[str, Any]]) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            insert_query = supabase_insert_minimal(client, table_name, batch)
            insert_query.execute()
            return
        except Exception as exc:
            last_error = exc
            if not is_transient_disconnect(exc) or attempt == 2:
                raise
            sleep(0.75 * (attempt + 1))
    if last_error:
        raise last_error


def execute_update_in_adaptive(
    client: Client,
    table_name: str,
    payload: dict[str, Any],
    match_column: str,
    match_values: list[Any],
) -> None:
    if not match_values:
        return
    try:
        execute_update_in(client, table_name, payload, match_column, match_values)
    except Exception as exc:
        if len(match_values) == 1 or not is_transient_disconnect(exc):
            raise
        midpoint = len(match_values) // 2
        sleep(0.5)
        execute_update_in_adaptive(client, table_name, payload, match_column, match_values[:midpoint])
        execute_update_in_adaptive(client, table_name, payload, match_column, match_values[midpoint:])


def execute_update_in(
    client: Client,
    table_name: str,
    payload: dict[str, Any],
    match_column: str,
    match_values: list[Any],
) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            rest_patch_update_in(table_name, payload, match_column, match_values)
            return
        except Exception as exc:
            last_error = exc
            if not is_transient_disconnect(exc) or attempt == 2:
                raise
            sleep(0.75 * (attempt + 1))
    if last_error:
        raise last_error


def upsert_batch_adaptive(
    client: Client,
    table_name: str,
    batch: list[dict[str, Any]],
    match_column: str,
) -> int:
    if not batch:
        return 0
    try:
        execute_upsert_batch(client, table_name, batch, match_column)
        return len(batch)
    except Exception as exc:
        if needs_unique_constraint(exc):
            raise RuntimeError(
                f"Bulk import needs a unique constraint on {table_name}.{match_column}. "
                f"Add the constraint in Supabase or choose id as the match column. Original error: {exc}"
            ) from exc
        if len(batch) == 1 or not is_transient_disconnect(exc):
            raise
        midpoint = len(batch) // 2
        sleep(0.5)
        return upsert_batch_adaptive(client, table_name, batch[:midpoint], match_column) + upsert_batch_adaptive(
            client,
            table_name,
            batch[midpoint:],
            match_column,
        )


def execute_upsert_batch(
    client: Client,
    table_name: str,
    batch: list[dict[str, Any]],
    match_column: str,
) -> None:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            upsert_query = supabase_upsert_minimal(client, table_name, batch, match_column)
            upsert_query.execute()
            return
        except Exception as exc:
            last_error = exc
            if not is_transient_disconnect(exc) or attempt == 2:
                raise
            sleep(0.75 * (attempt + 1))
    if last_error:
        raise last_error


def is_transient_disconnect(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        pattern in message
        for pattern in [
            "server disconnected",
            "connection",
            "timeout",
            "temporarily unavailable",
            "remote protocol error",
        ]
    )


def supabase_update_minimal(client: Client, table_name: str, payload: dict[str, Any]):
    try:
        return client.table(table_name).update(payload, returning="minimal")
    except TypeError:
        return client.table(table_name).update(payload)


def supabase_rest_config() -> tuple[str, str]:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured in st.secrets.")
    return str(url).rstrip("/"), str(key)


def rest_patch_update_in(
    table_name: str,
    payload: dict[str, Any],
    match_column: str,
    match_values: list[Any],
) -> None:
    url, key = supabase_rest_config()
    value_filter = ",".join(postgrest_value(value) for value in match_values)
    query = urlencode({match_column: f"in.({value_filter})"})
    endpoint = f"{url}/rest/v1/{quote(table_name, safe='')}?{query}"
    body = json.dumps(payload, default=str).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="PATCH",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    with urlopen(request, timeout=20) as response:
        if response.status >= 400:
            raise RuntimeError(f"Supabase update failed with status {response.status}.")


def postgrest_value(value: Any) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def supabase_upsert_minimal(
    client: Client,
    table_name: str,
    batch: list[dict[str, Any]],
    match_column: str,
):
    try:
        return client.table(table_name).upsert(
            batch,
            on_conflict=match_column,
            returning="minimal",
            default_to_null=False,
        )
    except TypeError:
        return client.table(table_name).upsert(
            batch,
            on_conflict=match_column,
            default_to_null=False,
        )


def supabase_insert_minimal(client: Client, table_name: str, batch: list[dict[str, Any]]):
    try:
        return client.table(table_name).insert(batch, returning="minimal")
    except TypeError:
        return client.table(table_name).insert(batch)


def needs_unique_constraint(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "42p10" in message
        or "on conflict" in message
        or "no unique" in message
        or "there is no unique" in message
        or "unique or exclusion constraint" in message
    )


def normalize_supabase_id(value: Any) -> Any:
    if is_empty_value(value):
        return None
    try:
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if not pd.isna(number) and float(number).is_integer():
            return int(number)
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def verify_saved_payload(
    client: Client,
    table_name: str,
    match_column: str,
    match_value: Any,
    payload: dict[str, Any],
) -> None:
    verify_columns = list(payload.keys())
    if not verify_columns:
        return
    response = (
        client.table(table_name)
        .select(select_columns(verify_columns))
        .eq(match_column, match_value)
        .limit(1)
        .execute()
    )
    saved_rows = response.data or []
    if not saved_rows:
        raise RuntimeError(f"Supabase did not return a saved row for {match_column} {match_value}.")
    saved = saved_rows[0]
    mismatched = [
        column
        for column, expected in payload.items()
        if not saved_value_matches(saved.get(column), expected)
    ]
    if mismatched:
        raise RuntimeError(
            "Supabase save verification failed for "
            f"{match_column} {match_value}. Columns not updated: {', '.join(mismatched)}."
        )


def saved_value_matches(actual: Any, expected: Any) -> bool:
    if is_empty_value(expected):
        return is_empty_value(actual)
    if is_empty_value(actual):
        return False
    expected_number = pd.to_numeric(pd.Series([expected]), errors="coerce").iloc[0]
    actual_number = pd.to_numeric(pd.Series([actual]), errors="coerce").iloc[0]
    if not pd.isna(expected_number) and not pd.isna(actual_number):
        return float(expected_number) == float(actual_number)
    return str(actual).strip() == str(expected).strip()


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


def unique_columns(columns: list[str]) -> list[str]:
    return list(dict.fromkeys(column for column in columns if column))


def reference_table_and_columns(key: str) -> tuple[str, list[str]]:
    if key == "students":
        return STUDENTS_TABLE, STUDENTS_WRITABLE_COLUMNS
    if key == "lecturers":
        return LECTURERS_TABLE, LECTURERS_WRITABLE_COLUMNS
    if key == "programs":
        return PROGRAMS_TABLE, PROGRAMS_WRITABLE_COLUMNS
    if key == "results":
        return RESULTS_TABLE, RESULTS_WRITABLE_COLUMNS
    if key == "assessments":
        return ASSESSMENTS_TABLE, ASSESSMENTS_WRITABLE_COLUMNS
    raise ValueError("Only existing Supabase tables can be edited: students, lecturers, programs, results, assessments.")


def natural_key_column(key: str) -> str:
    if key in ["students", "programs", "results"]:
        return "NO MATRIK"
    if key == "lecturers":
        return "KELAS"
    if key == "assessments":
        return "UJIAN"
    raise ValueError("Only existing Supabase tables can be edited: students, lecturers, programs, results, assessments.")


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
    update_columns: list[str] | None = None,
    match_column: str | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    df = raw.copy()
    duplicate_upload_columns = sorted({str(column) for column in df.columns[df.columns.duplicated()].tolist()})
    if duplicate_upload_columns:
        return df, [
            "Duplicate column name(s) found in the uploaded file: "
            f"{', '.join(duplicate_upload_columns)}. Remove duplicate headers and upload again."
        ]
    template_columns = create_upload_template(dataset_key, update_columns, match_column).columns.tolist()
    writable_columns = [column for column in template_columns if column != "id"]
    import_columns = [column for column in template_columns if column in df.columns]
    missing = [column for column in template_columns if column not in df.columns]
    errors = [f"Missing column: {column}" for column in missing]
    if errors:
        return df, errors

    df = df[import_columns].copy()
    for column in df.columns:
        df[column] = df[column].fillna("").astype(str).str.strip()

    required = required_import_columns(dataset_key, match_column)
    for row_number, row in df.iterrows():
        for column in required:
            if column not in row or row[column] == "":
                errors.append(f"Row {row_number + 2}: {column} is required")
        if dataset_key == "results":
            result_values = [
                row.get(column, "")
                for column in writable_columns
                if column not in ["id", "NO MATRIK"]
            ]
            if not any(value != "" for value in result_values):
                errors.append(f"Row {row_number + 2}: at least one result column is required")

    return df, errors


def required_import_columns(dataset_key: str, match_column: str | None = None) -> list[str]:
    if match_column:
        return [match_column]
    required = {
        "students": ["NO MATRIK", "NAMA PELAJAR", "KELAS", "SUBJEK"],
        "lecturers": ["KELAS", "PENSYARAH"],
        "programs": ["NO MATRIK", "PROGRAM"],
        "results": ["NO MATRIK"],
        "assessments": ["UJIAN"],
    }
    return required[dataset_key]


def create_upload_template(
    dataset_key: str = "students",
    update_columns: list[str] | None = None,
    match_column: str | None = None,
) -> pd.DataFrame:
    _, writable_columns = reference_table_and_columns(dataset_key)
    match = match_column or natural_key_column(dataset_key)
    selected_update_columns = update_columns or writable_columns
    columns = ["id"] if match == "id" else [match]
    for column in selected_update_columns:
        if column in writable_columns and column not in columns:
            columns.append(column)
    return pd.DataFrame(columns=columns)
