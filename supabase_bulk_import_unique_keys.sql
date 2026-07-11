-- Required once for reliable bulk import/upsert from the app.
-- Run this in Supabase SQL Editor.
--
-- Why:
-- The app uses Supabase upsert(..., on_conflict=<natural key>) in batches.
-- PostgreSQL requires each on_conflict column to have a UNIQUE constraint/index.

-- 1) Check for duplicate natural keys first.
-- If any rows appear here, fix/delete/merge those duplicates before creating indexes.
select 'students' as table_name, "NO MATRIK" as key_value, count(*) as duplicate_count
from public.students
where nullif(trim("NO MATRIK"), '') is not null
group by "NO MATRIK"
having count(*) > 1

union all

select 'results' as table_name, "NO MATRIK" as key_value, count(*) as duplicate_count
from public.results
where nullif(trim("NO MATRIK"), '') is not null
group by "NO MATRIK"
having count(*) > 1

union all

select 'programs' as table_name, "NO MATRIK" as key_value, count(*) as duplicate_count
from public.programs
where nullif(trim("NO MATRIK"), '') is not null
group by "NO MATRIK"
having count(*) > 1

union all

select 'lecturers' as table_name, "KELAS" as key_value, count(*) as duplicate_count
from public.lecturers
where nullif(trim("KELAS"), '') is not null
group by "KELAS"
having count(*) > 1

union all

select 'assessments' as table_name, "UJIAN" as key_value, count(*) as duplicate_count
from public.assessments
where nullif(trim("UJIAN"), '') is not null
group by "UJIAN"
having count(*) > 1

union all

select 'planning' as table_name, "NO MATRIK" as key_value, count(*) as duplicate_count
from public.planning
where nullif(trim("NO MATRIK"), '') is not null
group by "NO MATRIK"
having count(*) > 1;

-- 2) Create the unique indexes needed by app bulk import.
-- Run these only after the duplicate check above returns no rows.
create unique index if not exists students_no_matrik_unique_idx
on public.students ("NO MATRIK");

create unique index if not exists results_no_matrik_unique_idx
on public.results ("NO MATRIK");

create unique index if not exists programs_no_matrik_unique_idx
on public.programs ("NO MATRIK");

create unique index if not exists lecturers_kelas_unique_idx
on public.lecturers ("KELAS");

create unique index if not exists assessments_ujian_unique_idx
on public.assessments ("UJIAN");

create unique index if not exists planning_no_matrik_unique_idx
on public.planning ("NO MATRIK");
