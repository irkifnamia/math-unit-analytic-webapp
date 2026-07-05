create or replace function public.bulk_update_reference(
    p_table text,
    p_match_column text,
    p_update_column text,
    p_rows jsonb
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    allowed_columns text[] := array[
        'id',
        'NO MATRIK',
        'NAMA PELAJAR',
        'JURUSAN',
        'SISTEM',
        'KELAS',
        'SUBJEK',
        'PENSYARAH',
        'PROGRAM',
        'SPM_ADDMATH',
        'SPM_MATH',
        'PSPM_DM015',
        'PSPM_DM025',
        'AMAT_C1C2',
        'AMAT_C5',
        'AMAT_C8',
        'AMAT_C9C10',
        'PSPM_SEM1',
        'PSPM_SEM2'
    ];
    allowed_tables text[] := array['students', 'lecturers', 'programs', 'results'];
    update_type text;
    total_changed integer := 0;
    sql_text text;
begin
    if p_table is null or not p_table = any(allowed_tables) then
        raise exception 'Table % is not allowed for bulk update.', p_table;
    end if;

    if p_match_column is null or not p_match_column = any(allowed_columns) then
        raise exception 'Match column % is not allowed for bulk update.', p_match_column;
    end if;

    if p_update_column is null or not p_update_column = any(allowed_columns) then
        raise exception 'Update column % is not allowed for bulk update.', p_update_column;
    end if;

    select format_type(attribute.atttypid, attribute.atttypmod)
    into update_type
    from pg_attribute attribute
    join pg_class class on class.oid = attribute.attrelid
    join pg_namespace namespace on namespace.oid = class.relnamespace
    where namespace.nspname = 'public'
      and class.relname = p_table
      and attribute.attname = p_update_column
      and not attribute.attisdropped;

    if update_type is null then
        raise exception 'Update column %.% does not exist.', p_table, p_update_column;
    end if;

    sql_text := format(
        'with imported as (
            select match_value, update_value
            from jsonb_to_recordset($1) as imported(match_value text, update_value text)
        ),
        updated as (
            update %I target
            set %I = case
                    when imported.update_value is null or imported.update_value = '''' then null
                    else imported.update_value::%s
                end,
                updated_at = now()
            from imported
            where target.%I::text = imported.match_value
            returning 1
        )
        select count(*) from updated',
        p_table,
        p_update_column,
        update_type,
        p_match_column
    );

    execute sql_text using p_rows into total_changed;
    return total_changed;
end;
$$;

grant execute on function public.bulk_update_reference(text, text, text, jsonb) to anon, authenticated;
