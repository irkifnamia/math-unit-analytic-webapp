from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".python_packages")]

import pandas as pd

from services.supabase_store import SupabaseStore, clear_cached_reference_data


SYSTEM_VALUES = ["SES", "SDS"]
PROGRAM_VALUES = ["EMAS", "PERAK", "GANGSA"]
PSPM_VALUES = ["A", "A-", "B+", "B", "B-", "C+", "C"]
LECTURER_VALUES = [
    "AISYAH",
    "AMIR",
    "FARAH",
    "HAKIM",
    "INTAN",
    "KHAIRUL",
    "LINA",
    "NADIA",
    "RAHMAN",
    "SOFIA",
    "ZUL",
]

PSPM_COLUMNS = ["PSPM_DM015", "PSPM_DM025", "PSPM_SEM1", "PSPM_SEM2"]
AMAT_COLUMNS = ["AMAT_C1C2", "AMAT_C5", "AMAT_C8", "AMAT_C9C10"]


def is_blank(value: Any) -> bool:
    return value is None or pd.isna(value) or str(value).strip() == ""


def row_seed(row: pd.Series, fallback: int) -> int:
    value = row.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def choose(values: list[Any], seed: int, offset: int = 0) -> Any:
    return values[(seed + offset) % len(values)]


def amat_score(seed: int, offset: int = 0) -> int:
    return (seed * 17 + offset * 23) % 101


def build_payloads(
    df: pd.DataFrame,
    fillers: dict[str, Callable[[pd.Series, int], Any]],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        payload: dict[str, Any] = {"id": row["id"]}
        seed = row_seed(row, index)
        for column, filler in fillers.items():
            if column in df.columns and is_blank(row[column]):
                payload[column] = filler(row, seed)
        if len(payload) > 1:
            payloads.append(payload)
    return payloads


def upsert_batches(store: SupabaseStore, table: str, payloads: list[dict[str, Any]]) -> int:
    updated = 0
    for payload in payloads:
        record_id = payload["id"]
        changes = {key: value for key, value in payload.items() if key != "id"}
        if not changes:
            continue
        store.client.table(table).update(changes).eq("id", record_id).execute()
        updated += 1
    return updated


def update_column_blanks(
    store: SupabaseStore,
    table: str,
    df: pd.DataFrame,
    column: str,
    filler: Callable[[pd.Series, int], Any],
) -> int:
    if column not in df.columns:
        return 0

    groups: dict[Any, list[Any]] = {}
    for index, row in df.iterrows():
        if not is_blank(row[column]):
            continue
        seed = row_seed(row, index)
        value = filler(row, seed)
        groups.setdefault(value, []).append(row["id"])

    updated = 0
    for value, ids in groups.items():
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            store.client.table(table).update({column: value}).in_("id", chunk).execute()
            updated += len(chunk)
    return updated


def update_table_blanks(
    store: SupabaseStore,
    table: str,
    df: pd.DataFrame,
    fillers: dict[str, Callable[[pd.Series, int], Any]],
) -> int:
    updated = 0
    for column, filler in fillers.items():
        count = update_column_blanks(store, table, df, column, filler)
        print(f"{table}.{column}: filled {count} blank cell(s)")
        updated += count
    return updated


def main() -> None:
    store = SupabaseStore()
    refs = store.get_reference_data()

    table_updates = {
        "students": (
            refs["students"],
            {"SISTEM": lambda _row, seed: choose(SYSTEM_VALUES, seed)},
        ),
        "programs": (
            refs["programs"],
            {"PROGRAM": lambda _row, seed: choose(PROGRAM_VALUES, seed)},
        ),
        "lecturers": (
            refs["lecturers"],
            {"PENSYARAH": lambda _row, seed: choose(LECTURER_VALUES, seed)},
        ),
        "results": (
            refs["results"],
            {
                **{
                    column: (lambda _row, seed, offset=offset: choose(PSPM_VALUES, seed, offset))
                    for offset, column in enumerate(PSPM_COLUMNS)
                },
                **{
                    column: (lambda _row, seed, offset=offset: amat_score(seed, offset))
                    for offset, column in enumerate(AMAT_COLUMNS)
                },
            },
        ),
    }

    for table, (df, fillers) in table_updates.items():
        updated = update_table_blanks(store, table, df, fillers)
        print(f"{table}: filled {updated} blank cell(s)")

    clear_cached_reference_data()


if __name__ == "__main__":
    main()
