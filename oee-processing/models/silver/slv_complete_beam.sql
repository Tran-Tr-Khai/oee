{{
    config(
        materialized='incremental',
        unique_key=['date', 'machine', 'lot', 'shift', 'worker']
    )
}}

with source as (
    select *
    from {{ source('raw', 'raw_complete_beam') }}
),

typed as (
    select
        cast(try_cast(date as timestamp) as date) as date,
        {{ standardize_machine('machine') }} as machine,
        upper({{ clean_text('shift') }}) as shift,
        {{ clean_code('lot') }} as lot,
        try_cast(production_qty_kgs as double) as production_qty_kgs,
        try_cast(production_qty_mts as double) as production_qty_mts,
        {{ clean_text('worker') }} as worker,
        upper({{ clean_text('qty_unit') }}) as qty_unit
    from source
),

final as (
    select
        date,
        machine,
        shift,
        lot,
        production_qty_kgs,
        production_qty_mts,
        worker,
        qty_unit
    from typed
    where date is not null
      and machine is not null
      and lot is not null
)

select
    date,
    machine,
    shift,
    lot,
    production_qty_kgs,
    production_qty_mts,
    worker,
    qty_unit
from final
{% if is_incremental() %}
where not exists (
    select 1
    from {{ this }} existing
    where existing.date = final.date
      and existing.machine = final.machine
      and existing.lot = final.lot
      and coalesce(existing.shift, '__dbt_null__') = coalesce(final.shift, '__dbt_null__')
      and coalesce(existing.worker, '__dbt_null__') = coalesce(final.worker, '__dbt_null__')
)
{% endif %}
