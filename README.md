# Mathematic Unit Analytic

A professional Streamlit web application for managing and analyzing school or education-unit academic performance data from Supabase.

## Features

- IC Number login for Admin, Executive, and Lecturer users.
- Global filters across all pages for Pensyarah, Kelas, Subjek, and Sistem.
- Demography dashboard with KPI cards and Plotly visual analytics.
- SPM dashboard for Mathematics and Additional Mathematics, including grade distribution, trends, comparison charts, proportions, and a grade matrix.
- Admin-only data management with create, update, delete, CSV import, Excel import, validation, preview, and bulk update.
- Supabase-backed reads and CRUD. No local dummy academic data or mock datasets are created.

## Configuration

Create `.streamlit/secrets.toml` with:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-publishable-or-anon-key"
```

Optional table-name overrides are supported when the existing Supabase schema uses different names:

```toml
SUPABASE_TABLE_RECORDS = "students"
SUPABASE_TABLE_STUDENTS = "students"
SUPABASE_TABLE_LECTURERS = "lecturers"
SUPABASE_TABLE_PROGRAMS = "programs"
SUPABASE_TABLE_CLASSES = "classes"
SUPABASE_TABLE_SUBJECTS = "subjects"
SUPABASE_TABLE_SYSTEMS = "systems"
SUPABASE_TABLE_PROFILES = "profiles"
```

User roles come from the IC allowlist. Missing roles default to the least-privileged Lecturer role.

## Supabase Columns

The app uses only the existing Supabase tables and these exact columns:

`students`:

```text
id
created_at
NO MATRIK
NAMA PELAJAR
JURUSAN
SISTEM
KELAS
SUBJEK
updated_at
```

`lecturers`:

```text
id
created_at
updated_at
KELAS
PENSYARAH
```

`programs`:

```text
id
created_at
updated_at
NO MATRIK
PROGRAM
```

Any missing/nonexistent field is skipped rather than queried or written.

Temporary IC login is enabled until the official allowlist is ready:

| Role | IC Number |
| --- | --- |
| Admin | `900101145555` |
| Executive | `850505105555` |
| Lecturer | `880808085555` |

Later, configure the official allowlist in `.streamlit/secrets.toml`:

```toml
[ALLOWED_IC_USERS."900101145555"]
full_name = "Admin Name"
role = "Admin"

[ALLOWED_IC_USERS."850505105555"]
full_name = "Executive Name"
role = "Executive"

[ALLOWED_IC_USERS."880808085555"]
full_name = "Lecturer Name"
role = "Lecturer"
lecturer_name = "Lecturer Name In Supabase"
```

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The application reads existing Supabase data only. It does not create seed data.

If the local `.venv` points to a missing Python installation, this project can also run with the verified fallback package folder:

```powershell
& "C:\Program Files\PostgreSQL\15\pgAdmin 4\python\python.exe" run_app.py
```

## Bulk Import

Open **Data Management > Bulk Import** as an Admin and download the CSV template. Supported upload formats:

- `.csv`
- `.xlsx`
- `.xls`

Required columns:

```text
student_no, student_name, gender, class, program, subject, lecturer, system, year, term, math_score, addmath_score, spm_math_grade, spm_addmath_grade
```

Records are upserted by student, year, term, and subject.
