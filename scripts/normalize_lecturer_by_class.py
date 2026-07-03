from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".python_packages")]

import pandas as pd

from services.supabase_store import SupabaseStore, clear_cached_reference_data


LECTURER_VALUES = [
    "SURIA",
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


def main() -> None:
    store = SupabaseStore()
    lecturers = store.get_core_reference_data()["lecturers"]
    classes = sorted(
        kelas
        for kelas in lecturers["KELAS"].dropna().astype(str).str.strip().unique().tolist()
        if kelas
    )

    updated_rows = 0
    for index, kelas in enumerate(classes):
        lecturer = LECTURER_VALUES[index % len(LECTURER_VALUES)]
        matched = lecturers[lecturers["KELAS"].astype(str).str.strip() == kelas]
        store.client.table("lecturers").update({"PENSYARAH": lecturer}).eq("KELAS", kelas).execute()
        updated_rows += len(matched)

    clear_cached_reference_data()

    refreshed = SupabaseStore().get_core_reference_data()["lecturers"]
    conflict_count = (
        refreshed.groupby("KELAS")["PENSYARAH"]
        .agg(lambda values: len(set(value for value in values.dropna().astype(str).str.strip() if value)))
        .gt(1)
        .sum()
    )
    print(f"classes: {len(classes)}")
    print(f"updated_rows: {updated_rows}")
    print(f"classes_with_multiple_lecturers: {int(conflict_count)}")


if __name__ == "__main__":
    main()
